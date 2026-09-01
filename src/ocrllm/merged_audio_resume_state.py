"""Strict schema for one explicit merged-audio recognition sidecar."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass

from .audio.build_long_audio_interval_prompt import (
    LONG_AUDIO_INTERVAL_PROMPT_VERSION,
)
from .audio.build_long_audio_interval_windows import (
    LongAudioIntervalWindow,
    build_long_audio_interval_windows,
)
from .audio.transcription_prompt import AUDIO_TRANSCRIPTION_PROMPT_VERSION
from .contracts.source_fingerprint import SourceFingerprint
from .errors import ResumeStateError
from .provider_model_usage import ProviderModelUsage


MERGED_AUDIO_RESUME_STATE_VERSION = "ocrllm.merged-audio-resume.v1"
_SLOT_STATUSES = frozenset({"unresolved", "settled", "failed"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ROOT_KEYS = frozenset(
    {
        "state_version",
        "mode",
        "interval_minutes",
        "prompt_version",
        "source",
        "slots",
        "usage",
        "provider_cleanup_failed",
    }
)
_SOURCE_KEYS = frozenset({"uri", "byte_size", "sha256"})
_SLOT_KEYS = frozenset(
    {
        "index",
        "logical_start_seconds",
        "logical_end_seconds",
        "actual_start_seconds",
        "actual_end_seconds",
        "status",
        "no_speech",
        "markdown",
        "markdown_sha256",
        "vendor",
        "model",
        "error_code",
        "error_description",
    }
)
_USAGE_KEYS = frozenset(
    {"vendor", "model", "calls", "input_tokens", "output_tokens"}
)


@dataclass(frozen=True, slots=True, kw_only=True)
class MergedAudioSlot:
    """Store one immutable audio range and its latest terminal outcome."""

    index: int
    logical_start_seconds: float
    logical_end_seconds: float
    actual_start_seconds: float
    actual_end_seconds: float
    status: str = "unresolved"
    no_speech: bool = False
    markdown: str | None = None
    markdown_sha256: str | None = None
    vendor: str | None = None
    model: str | None = None
    error_code: str | None = None
    error_description: str | None = None

    def __post_init__(self) -> None:
        if type(self.index) is not int or self.index < 0:
            raise ValueError("merged-audio slot index is invalid")
        boundaries = (
            self.logical_start_seconds,
            self.logical_end_seconds,
            self.actual_start_seconds,
            self.actual_end_seconds,
        )
        if any(
            type(value) not in (int, float) or not math.isfinite(float(value))
            for value in boundaries
        ) or not (
            0.0 <= self.actual_start_seconds
            <= self.logical_start_seconds
            < self.logical_end_seconds
            <= self.actual_end_seconds
        ):
            raise ValueError("merged-audio slot boundaries are invalid")
        if type(self.status) is not str or self.status not in _SLOT_STATUSES:
            raise ValueError("merged-audio slot status is invalid")
        if type(self.no_speech) is not bool:
            raise ValueError("merged-audio no-speech state is invalid")
        if self.status == "settled":
            if not _is_text(self.vendor) or not _is_text(self.model):
                raise ValueError("settled merged-audio provider identity is invalid")
            if self.error_code is not None or self.error_description is not None:
                raise ValueError("settled merged-audio slot carries an error")
            if self.no_speech:
                if self.markdown is not None or self.markdown_sha256 is not None:
                    raise ValueError("no-speech merged-audio slot carries Markdown")
            elif (
                not _is_text(self.markdown)
                or type(self.markdown_sha256) is not str
                or _SHA256.fullmatch(self.markdown_sha256) is None
                or self.markdown_sha256
                != hashlib.sha256(self.markdown.encode("utf-8")).hexdigest()
            ):
                raise ValueError("settled merged-audio Markdown is invalid")
        elif self.status == "failed":
            if (
                self.no_speech
                or self.markdown is not None
                or self.markdown_sha256 is not None
                or not _is_text(self.vendor)
                or not _is_text(self.model)
                or not _is_text(self.error_code)
                or not _is_text(self.error_description)
            ):
                raise ValueError("failed merged-audio slot is invalid")
        elif (
            self.no_speech
            or any(
                value is not None
                for value in (
                    self.markdown,
                    self.markdown_sha256,
                    self.vendor,
                    self.model,
                    self.error_code,
                    self.error_description,
                )
            )
        ):
            raise ValueError("unresolved merged-audio slot carries outcome data")


@dataclass(frozen=True, slots=True, kw_only=True)
class MergedAudioResumeState:
    """Store one fixed audio-slice plan and every reusable slot outcome."""

    state_version: str
    mode: str
    interval_minutes: int | None
    prompt_version: str
    source: SourceFingerprint
    slots: tuple[MergedAudioSlot, ...]
    usage: tuple[ProviderModelUsage, ...] = ()
    provider_cleanup_failed: bool = False

    def __post_init__(self) -> None:
        if self.state_version != MERGED_AUDIO_RESUME_STATE_VERSION:
            raise ValueError("merged-audio resume state version is unsupported")
        if type(self.source) is not SourceFingerprint:
            raise ValueError("merged-audio source is invalid")
        if (
            type(self.slots) is not tuple
            or not self.slots
            or any(type(value) is not MergedAudioSlot for value in self.slots)
            or tuple(slot.index for slot in self.slots) != tuple(range(len(self.slots)))
        ):
            raise ValueError("merged-audio slots are invalid")
        self._validate_plan()
        if (
            type(self.usage) is not tuple
            or any(type(value) is not ProviderModelUsage for value in self.usage)
            or len({(value.vendor, value.model) for value in self.usage})
            != len(self.usage)
        ):
            raise ValueError("merged-audio usage rows are invalid")
        if type(self.provider_cleanup_failed) is not bool:
            raise ValueError("merged-audio cleanup state is invalid")

    def _validate_plan(self) -> None:
        if self.mode == "whole":
            slot = self.slots[0]
            if (
                len(self.slots) != 1
                or self.interval_minutes is not None
                or self.prompt_version != AUDIO_TRANSCRIPTION_PROMPT_VERSION
                or slot.logical_start_seconds != 0.0
                or slot.actual_start_seconds != 0.0
                or slot.logical_end_seconds != slot.actual_end_seconds
            ):
                raise ValueError("whole merged-audio plan is invalid")
            return
        if (
            self.mode != "interval"
            or type(self.interval_minutes) is not int
            or self.interval_minutes <= 0
            or self.prompt_version != LONG_AUDIO_INTERVAL_PROMPT_VERSION
        ):
            raise ValueError("interval merged-audio plan is invalid")
        expected_plans = tuple(
            build_long_audio_interval_windows(
                duration_seconds=self.slots[-1].logical_end_seconds,
                interval_minutes=self.interval_minutes,
                include_boundary_context=include_boundary_context,
            )
            for include_boundary_context in (True, False)
        )
        if not any(
            _slots_match_windows(self.slots, expected)
            for expected in expected_plans
        ):
            raise ValueError("interval merged-audio ranges are invalid")
    def to_bytes(self) -> bytes:
        """Return deterministic secret-free UTF-8 JSON."""
        document = {
            "state_version": self.state_version,
            "mode": self.mode,
            "interval_minutes": self.interval_minutes,
            "prompt_version": self.prompt_version,
            "source": {
                "uri": self.source.uri,
                "byte_size": self.source.byte_size,
                "sha256": self.source.sha256,
            },
            "slots": [
                {
                    "index": slot.index,
                    "logical_start_seconds": slot.logical_start_seconds,
                    "logical_end_seconds": slot.logical_end_seconds,
                    "actual_start_seconds": slot.actual_start_seconds,
                    "actual_end_seconds": slot.actual_end_seconds,
                    "status": slot.status,
                    "no_speech": slot.no_speech,
                    "markdown": slot.markdown,
                    "markdown_sha256": slot.markdown_sha256,
                    "vendor": slot.vendor,
                    "model": slot.model,
                    "error_code": slot.error_code,
                    "error_description": slot.error_description,
                }
                for slot in self.slots
            ],
            "usage": [
                {
                    "vendor": row.vendor,
                    "model": row.model,
                    "calls": row.calls,
                    "input_tokens": row.input_tokens,
                    "output_tokens": row.output_tokens,
                }
                for row in self.usage
            ],
            "provider_cleanup_failed": self.provider_cleanup_failed,
        }
        return (
            json.dumps(
                document,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")

    @classmethod
    def from_bytes(cls, raw: bytes) -> MergedAudioResumeState:
        """Reject duplicate keys, schema drift, and invalid slot content."""
        try:
            if type(raw) is not bytes:
                raise ValueError
            document = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
            return _state_from_document(document)
        except ResumeStateError:
            raise
        except Exception:
            raise ResumeStateError(
                "The merged-audio resume state is corrupt or unsupported.",
                code="RESUME_STATE_INVALID",
            ) from None


def _slots_match_windows(
    slots: tuple[MergedAudioSlot, ...],
    windows: tuple[LongAudioIntervalWindow, ...],
) -> bool:
    if len(windows) != len(slots):
        return False
    return all(
        slot.index == window.index
        and slot.logical_start_seconds == window.logical_start_seconds
        and slot.logical_end_seconds == window.logical_end_seconds
        and slot.actual_start_seconds == window.actual_start_seconds
        and slot.actual_end_seconds == window.actual_end_seconds
        for slot, window in zip(slots, windows, strict=True)
    )


def _state_from_document(document: object) -> MergedAudioResumeState:
    if type(document) is not dict or frozenset(document) != _ROOT_KEYS:
        raise ValueError
    source_document = document["source"]
    slot_documents = document["slots"]
    usage_documents = document["usage"]
    if (
        type(source_document) is not dict
        or frozenset(source_document) != _SOURCE_KEYS
        or type(slot_documents) is not list
        or type(usage_documents) is not list
    ):
        raise ValueError
    source = SourceFingerprint(
        uri=source_document["uri"],
        byte_size=source_document["byte_size"],
        sha256=source_document["sha256"],
    )
    slots = []
    for slot in slot_documents:
        if type(slot) is not dict or frozenset(slot) != _SLOT_KEYS:
            raise ValueError
        slots.append(
            MergedAudioSlot(
                index=slot["index"],
                logical_start_seconds=slot["logical_start_seconds"],
                logical_end_seconds=slot["logical_end_seconds"],
                actual_start_seconds=slot["actual_start_seconds"],
                actual_end_seconds=slot["actual_end_seconds"],
                status=slot["status"],
                no_speech=slot["no_speech"],
                markdown=slot["markdown"],
                markdown_sha256=slot["markdown_sha256"],
                vendor=slot["vendor"],
                model=slot["model"],
                error_code=slot["error_code"],
                error_description=slot["error_description"],
            )
        )
    usage = []
    for row in usage_documents:
        if type(row) is not dict or frozenset(row) != _USAGE_KEYS:
            raise ValueError
        usage.append(
            ProviderModelUsage(
                vendor=row["vendor"],
                model=row["model"],
                calls=row["calls"],
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
            )
        )
    return MergedAudioResumeState(
        state_version=document["state_version"],
        mode=document["mode"],
        interval_minutes=document["interval_minutes"],
        prompt_version=document["prompt_version"],
        source=source,
        slots=tuple(slots),
        usage=tuple(usage),
        provider_cleanup_failed=document["provider_cleanup_failed"],
    )


def _is_text(value: object) -> bool:
    return type(value) is str and bool(value.strip())


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _reject_constant(_value: str) -> object:
    raise ValueError
