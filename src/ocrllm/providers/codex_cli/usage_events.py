"""Durable, opt-in public Codex usage facts; never a recognition checkpoint."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from threading import Lock
import uuid

from ...errors import OutputError
from ...observation_context import _FIELDS, _OBSERVER

_LOCK = Lock()
_INSTANCE = uuid.uuid4().hex
_USAGE_FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")


def now():
    return datetime.now(timezone.utc).isoformat()


class CodexUsageAttempt:
    """One CLI spawn intent and its own incremental turn usage stream."""

    def __init__(self, *, settings, model, source_paths, parent_call_id):
        fields = _FIELDS.get()
        observer = _OBSERVER.get() or {}
        sources = list(fields.get("source_paths") or map(str, source_paths))
        self.directory = settings.usage_event_dir
        self.spawned = False
        self.common = {
            "attempt_id": uuid.uuid4().hex, "parent_call_id": parent_call_id,
            "lecture_id": observer.get("lecture_id") or fields.get("lecture_id"),
            "logical_unit_id": fields.get("logical_unit_id") or hashlib.sha256(json.dumps(sources).encode()).hexdigest(),
            "start_event_id": uuid.uuid4().hex, "started_at": now(),
            "requested_model": model, "reasoning_effort": settings.reasoning_effort,
            "requested_service_tier": settings.service_tier or ("priority" if settings.fast_mode else None),
            "actual_model": None, "actual_service_tier": None, "actual_reasoning_effort": None,
            "source_refs": sources, "input_image_count": len(source_paths),
            "cli_version": fields.get("cli_version"),
            "ocrllm_version": observer.get("runtime_version") or fields.get("runtime_version"),
            "prompt_version": fields.get("prompt_version"),
            "configured_concurrency": fields.get("configured_concurrency"),
        }
        self.turns = []
        self.thread_id = None
        self.active_turn = False
        self.terminal_failed = False
        self.stream_complete = True
        self._terminal_ids = {}
        self._cumulative = {None: dict.fromkeys(_USAGE_FIELDS, 0)}

    def emit(self, kind, *, event_id=None, **data):
        if self.directory is None:
            return
        event = {
            "schema_version": "course-observation/v1", "owner": "ocrllm", "task": "ocr",
            "event_id": event_id or uuid.uuid4().hex, "kind": kind, "at": now(),
            "instance_id": f"{os.getpid()}-{_INSTANCE}", "data": {**self.common, **data},
        }
        try:
            line = json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n"
            directory = Path(self.directory)
            with _LOCK:
                directory.mkdir(parents=True, exist_ok=True)
                destination = directory / f"codex-{os.getpid()}-{_INSTANCE}.jsonl"
                created = not destination.exists()
                with destination.open("a", encoding="utf-8") as stream:
                    stream.write(line)
                    stream.flush()
                    os.fsync(stream.fileno())
                if created and os.name == "posix":
                    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
        except (OSError, TypeError, ValueError):
            raise OutputError(
                "Codex usage events could not be persisted; no further request was admitted.",
                details={"reason": "codex_usage_write_failed", "attempt_id": self.common["attempt_id"]},
            ) from None

    def started(self):
        self.emit("codex_attempt_started", event_id=self.common["start_event_id"],
                  spawned=None, outcome="running", validation_status="unknown", usage_capture_complete=False)

    def consume_line(self, line):
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            self.stream_complete = False
            return
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            self.stream_complete = False
            return
        event_type = event["type"]
        # Only explicit server values are actuals. Requested settings are never
        # substituted for missing execution facts.
        for source, target in (("model", "actual_model"), ("service_tier", "actual_service_tier"),
                               ("reasoning_effort", "actual_reasoning_effort")):
            value = _safe_text(event.get(source))
            if value is not None and event_type in ("turn.started", "turn.completed", "turn.failed"):
                self.common[target] = value
        if event_type == "thread.started":
            self.thread_id = _safe_text(event.get("thread_id"))
            self._cumulative.setdefault(self.thread_id, dict.fromkeys(_USAGE_FIELDS, 0))
        if event_type == "turn.started":
            if self.active_turn:
                self._turn("turn.interrupted", None, "terminal_event_missing")
            self.active_turn = True
        if event_type in ("turn.completed", "turn.failed"):
            self.terminal_failed = event_type == "turn.failed"
            turn_id = _safe_text(event.get("turn_id"))
            # A reported stable identity is stronger than line order. Never bill
            # an identical retransmission twice, or silently replace a conflict.
            if turn_id is not None and turn_id in self._terminal_ids:
                if self._terminal_ids[turn_id] != event.get("usage"):
                    self.stream_complete = False
                return
            if turn_id is not None:
                self._terminal_ids[turn_id] = event.get("usage")
            self._turn(event_type, event.get("usage"), "usage_not_reported", turn_id=turn_id)
            self.active_turn = False

    def _turn(self, event_type, raw_usage, missing_reason, *, turn_id=None):
        raw_usage = raw_usage if isinstance(raw_usage, dict) else {}
        reported = {key: value if type(value := raw_usage.get(key)) is int and value >= 0 else None
                    for key in _USAGE_FIELDS}
        baseline = self._cumulative[self.thread_id]
        # The verified CLI emitter reads ThreadTokenUsage.total, despite the
        # public event type's "during a turn" comment. Fresh exec starts at 0;
        # later events need per-field differences in the same thread. A missing
        # baseline is unknown, never a license to bill a later total as a delta.
        usage = {key: value - baseline[key]
                 if value is not None and baseline[key] is not None and value >= baseline[key]
                 else None for key, value in reported.items()}
        self._cumulative[self.thread_id] = reported
        problems = [key for key, value in usage.items() if value is None]
        for subset, total in (("cached_input_tokens", "input_tokens"), ("reasoning_output_tokens", "output_tokens")):
            if usage[subset] is not None and usage[total] is not None and usage[subset] > usage[total]:
                usage[subset] = None
                problems.append(subset)
        data = {
            "turn_seq": len(self.turns), "event_type": event_type, "observed_at": now(),
            "usage_semantics_version": "codex-turn-usage/v1", "usage": usage,
            "raw_usage": reported, "raw_usage_scope": "thread_cumulative",
            "normalization": "thread_cumulative_delta",
            "missing_reason": (missing_reason + ":" + ",".join(problems)) if problems else None,
            "thread_id": self.thread_id, "reported_turn_id": turn_id,
        }
        if "cache_write_input_tokens" in raw_usage:
            value = raw_usage["cache_write_input_tokens"]
            data["raw_usage"] = {**reported, "cache_write_input_tokens": value if type(value) is int and value >= 0 else None}
        self.emit("codex_turn_usage", **data)
        self.turns.append(usage)

    def finish(self, *, spawned, exit_code, outcome, validation_status, error_code=None):
        if spawned and (self.active_turn or not self.turns):
            self._turn("process.finished", None, "terminal_usage_missing")
            self.active_turn = False
        totals = {key: (sum(row[key] for row in self.turns)
                       if not spawned or self.stream_complete and self.turns and all(row[key] is not None for row in self.turns)
                       else None) for key in ("input_tokens", "output_tokens")}
        complete = all(value is not None for value in totals.values())
        self.emit("codex_attempt_finished", spawned=int(spawned), exit_code=exit_code,
                  outcome=outcome, validation_status=validation_status, finished_at=now(),
                  usage_capture_complete=complete, error_code=error_code)
        return totals

    def preserve_failed_output(self, output_path):
        """Keep inspectable failed Markdown separately from the usage ledger."""
        if self.directory is None or not Path(output_path).exists():
            return
        try:
            content = Path(output_path).read_bytes()
            directory = Path(self.directory) / "failure_outputs"
            directory.mkdir(parents=True, exist_ok=True)
            destination = directory / (self.common["attempt_id"] + ".md")
            with destination.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            if os.name == "posix":
                descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            self.common["failure_output_path"] = str(destination)
            self.common["failure_output_sha256"] = hashlib.sha256(content).hexdigest()
        except OSError:
            raise OutputError("The failed Codex output could not be persisted.",
                              details={"reason": "codex_failure_output_write_failed"}) from None


def _safe_text(value):
    return value if type(value) is str and 0 < len(value) <= 256 and all(ord(c) >= 32 for c in value) else None
