"""Run one Codex CLI vision batch with durable per-attempt usage."""
from __future__ import annotations

import shutil
import tempfile
import time
import uuid
from collections.abc import Sequence
from pathlib import Path

from ...config import Config
from ...cooperative_stop import ProviderDispatchStopped
from ...errors import ConfigError, OCRLLMError, ProviderError, ProviderRequestInvalid, ProviderUnavailable
from ...raise_if_cancelled import raise_if_cancelled
from ..validate_provider_markdown import validate_provider_markdown
from ..vision_provider_response import VisionProviderResponse
from .build_codex_exec_command import build_codex_exec_command, build_codex_exec_prompt
from .call_control import remaining_seconds, stop_requested
from .codex_exec_output import is_image_access_refusal, parse_codex_refusal, summarize_codex_failure_output
from .provider_settings import CodexCLISettings, resolve_codex_cli_model
from .read_cli_version import read_cli_version
from .run_codex_process import run_codex_process
from .stage_codex_images import stage_codex_images
from .usage_events import CodexUsageAttempt

_MAX_ATTEMPTS = 3
_RETRY_DELAY_SECONDS = 4.0
_IMAGE_ACCESS_RETRY_DELAYS_SECONDS = (15.0, 45.0, 90.0, 180.0, 300.0)


def recognize_images(image_paths: Sequence[Path], *, prompt: str, config: Config) -> VisionProviderResponse:
    """Finish admitted calls; persist each attempt before retry or safe drain.

    The adapter timeout bounds each subprocess. The merged bridge also supplies
    an absolute call deadline, including internal backoff and retries. CLI JSON
    stdout is solely usage telemetry; only --output-last-message is Markdown.
    """
    settings = config.provider
    if type(settings) is not CodexCLISettings:
        raise ConfigError("The built-in Codex CLI provider requires exact CodexCLISettings.",
                          code="CONFIG_INVALID", details={"provider_calls_attempted": 0})
    model = resolve_codex_cli_model(config.vision_model.name, settings)
    resolved_command = shutil.which(settings.command)
    if resolved_command is None:
        raise ConfigError("The Codex CLI command is not available on PATH.", code="CONFIG_MISSING",
                          details={"provider": "codex_cli", "provider_calls_attempted": 0})
    if len(image_paths) > settings.max_images_per_call:
        raise ProviderRequestInvalid(f"The Codex CLI provider accepts at most {settings.max_images_per_call} images per call.",
                                     details={"provider": "codex_cli", "model": model, "provider_calls_attempted": 0})
    if stop_requested():
        raise ProviderDispatchStopped()
    raise_if_cancelled(config.cancellation)
    cli_version = read_cli_version(resolved_command)
    parent_call_id = uuid.uuid4().hex
    calls = 0
    totals = {"input_tokens": 0, "output_tokens": 0}
    with tempfile.TemporaryDirectory(prefix="ocrllm_codex_") as tmp:
        staging_dir = Path(tmp)
        try:
            staged_paths = stage_codex_images(image_paths, staging_dir)
        except OCRLLMError as error:
            error._add_safe_detail("provider_calls_attempted", 0)
            raise
        output_path = staging_dir / "last_message.txt"
        argv = build_codex_exec_command(
            command=resolved_command, model=model, reasoning_effort=settings.reasoning_effort,
            fast_mode=settings.fast_mode, service_tier=settings.service_tier, image_paths=staged_paths,
            cwd=staging_dir, output_path=output_path,
            prompt=build_codex_exec_prompt(prompt, len(staged_paths), source_names=tuple(path.name for path in image_paths)),
        )
        regular_attempt = 0
        image_access_retries = 0
        last_error = None
        while regular_attempt < _MAX_ATTEMPTS:
            if stop_requested():
                if last_error is not None:
                    raise _with_usage(last_error, calls, totals)
                raise ProviderDispatchStopped()
            raise_if_cancelled(config.cancellation)
            timeout = remaining_seconds(settings.timeout_seconds)
            if timeout <= 0:
                error = last_error or ProviderError("The Codex CLI call deadline elapsed before admission.", code="PROVIDER_TIMEOUT", retryable=True)
                raise _with_usage(error, calls, totals)
            regular_attempt += 1
            output_path.unlink(missing_ok=True)
            observation = CodexUsageAttempt(settings=settings, model=model, source_paths=image_paths, parent_call_id=parent_call_id)
            observation.common.update(cli_version=cli_version, cli_binary_path=str(Path(resolved_command).resolve()))
            observation.started()
            if stop_requested():
                observation.finish(spawned=False, exit_code=None, outcome="cancelled", validation_status="not_run")
                if last_error is not None:
                    raise _with_usage(last_error, calls, totals)
                raise ProviderDispatchStopped()
            timeout = remaining_seconds(settings.timeout_seconds)
            if timeout <= 0:
                observation.finish(spawned=False, exit_code=None, outcome="timed_out", validation_status="not_run", error_code="PROVIDER_TIMEOUT")
                error = last_error or ProviderError("The Codex CLI call deadline elapsed before admission.", code="PROVIDER_TIMEOUT", retryable=True)
                raise _with_usage(error, calls, totals)
            delay = None
            outcome = "failed"
            validation = "not_run"
            exit_code = None
            error = None
            try:
                exit_code, diagnostic, timed_out = run_codex_process(argv, timeout_seconds=timeout, attempt=observation)
            except OCRLLMError as fatal:
                fatal._add_safe_detail("provider_calls_attempted", calls + int(observation.spawned))
                raise
            except OSError as exc:
                error = ProviderUnavailable("The Codex CLI process could not be started.",
                    details={"description": _single_line(str(exc))})
                if regular_attempt < _MAX_ATTEMPTS:
                    delay = max(10.0, _RETRY_DELAY_SECONDS * regular_attempt * 3)
            else:
                if timed_out:
                    outcome = "timed_out"
                    error = ProviderError("The Codex CLI recognition exceeded its timeout.", code="PROVIDER_TIMEOUT", retryable=True,
                                          details={"timeout_seconds": timeout})
                elif exit_code != 0 or observation.terminal_failed:
                    error = ProviderUnavailable("The Codex CLI recognition failed after repeated attempts.",
                        details={"description": summarize_codex_failure_output(diagnostic, exit_code)})
                    if regular_attempt < _MAX_ATTEMPTS:
                        delay = _RETRY_DELAY_SECONDS * regular_attempt
                else:
                    decode_error = False
                    try:
                        text = output_path.read_text(encoding="utf-8").strip()
                    except UnicodeError:
                        text = ""
                        decode_error = True
                    except OSError:
                        text = ""
                    refusal = parse_codex_refusal(text) if text else None
                    if decode_error:
                        validation = "rejected"
                        error = ProviderError("The Codex CLI returned invalid Unicode.", code="PROVIDER_RESPONSE_INVALID",
                                              details={"reason": "invalid_unicode"})
                    elif refusal is not None:
                        validation = "rejected"
                        if is_image_access_refusal(refusal):
                            error = ProviderUnavailable("The Codex CLI backend lost the staged image attachments; the batch can be resumed later.",
                                                        details={"reason": "image_access", "description": _single_line(refusal, 200)})
                            if image_access_retries < len(_IMAGE_ACCESS_RETRY_DELAYS_SECONDS):
                                delay = _IMAGE_ACCESS_RETRY_DELAYS_SECONDS[image_access_retries]
                                image_access_retries += 1
                                regular_attempt -= 1
                        else:
                            error = ProviderError("The Codex CLI model declined the recognition request.", code="PROVIDER_REFUSED_RECOGNITION",
                                                  details={"reason": "refusal", "description": _single_line(refusal, 200)})
                            if regular_attempt < _MAX_ATTEMPTS:
                                delay = _RETRY_DELAY_SECONDS * regular_attempt
                    else:
                        try:
                            text = validate_provider_markdown(text)
                            if settings.course_validation:
                                from .validate_codex_course_markdown import validate_codex_course_markdown
                                text = validate_codex_course_markdown(text, tuple(path.name for path in image_paths),
                                    adjacent_repeat_limit=settings.adjacent_repeat_limit)
                                text = validate_provider_markdown(text)
                        except ProviderError as invalid:
                            error = invalid
                            validation = "rejected"
                            # Preserve existing empty-response recovery; permanent
                            # content validation remains a settled failed attempt.
                            if invalid.details.get("reason") == "empty" and regular_attempt < _MAX_ATTEMPTS:
                                delay = _RETRY_DELAY_SECONDS * regular_attempt
                        else:
                            outcome = "succeeded"
                            validation = "accepted"
            calls += int(observation.spawned)
            if error is not None:
                observation.preserve_failed_output(output_path)
                for key in ("failure_output_path", "failure_output_sha256"):
                    if key in observation.common:
                        error._add_safe_detail(key, observation.common[key])
            usage = observation.finish(spawned=observation.spawned, exit_code=exit_code, outcome=outcome,
                                       validation_status=validation, error_code=error.code if error else None)
            for key in totals:
                totals[key] = totals[key] + usage[key] if totals[key] is not None and usage[key] is not None else None
            if error is None:
                return VisionProviderResponse(markdown=text, input_tokens=totals["input_tokens"], output_tokens=totals["output_tokens"],
                                              provider_calls_attempted=calls)
            error._add_safe_detail("provider", "codex_cli")
            error._add_safe_detail("model", model)
            last_error = error
            # The completed failure must reach the checkpoint owner before stop
            # acknowledgment. Do not replace it with an internal cancellation.
            if delay is None or stop_requested():
                raise _with_usage(error, calls, totals)
            _sleep_with_cancellation(delay, config.cancellation)
        raise _with_usage(last_error, calls, totals)


def _with_usage(error, calls, totals):
    error._add_safe_detail("provider_calls_attempted", calls)
    for key, value in totals.items():
        error._add_safe_detail(key, value)
    return error


def _sleep_with_cancellation(seconds, cancellation):
    deadline = time.monotonic() + min(seconds, max(0.0, remaining_seconds(seconds)))
    while not stop_requested():
        raise_if_cancelled(cancellation)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(remaining, 0.2))


def _single_line(text, limit=500):
    return " ".join((text or "").split())[:limit]
