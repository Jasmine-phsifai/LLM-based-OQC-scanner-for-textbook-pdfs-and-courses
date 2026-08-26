"""Run one bounded, credential-safe Google GenAI audio live gate."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ocrllm import (
    AudioModelSettings,
    Config,
    GoogleGenAISettings,
    list_google_genai_models,
    recognize,
    recognize_long_mp3,
)
from ocrllm.errors import ConfigError, OCRLLMError, ProviderError
from ocrllm.provider_error_disposition import get_provider_error_disposition


class _LiveSmokeFailure(Exception):
    """Keep a runner stage beside, not inside, a public product error."""

    def __init__(self, stage: str, error: OCRLLMError | None) -> None:
        self.stage = stage
        self.error = error
        super().__init__(stage)


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse one explicit model, MP3 path, and timeout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--long",
        action="store_true",
        help="Use the standalone Google Files route and require more than 300 seconds.",
    )
    parser.add_argument("--interval-minutes", type=_positive_integer)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--resume", action="store_true")
    arguments = parser.parse_args(argv)
    if arguments.interval_minutes is not None and not arguments.long:
        parser.error("--interval-minutes requires --long")
    if (arguments.interval_minutes is None) != (arguments.output_dir is None):
        parser.error("--interval-minutes and --output-dir must be used together")
    if arguments.resume and arguments.interval_minutes is None:
        parser.error("--resume requires interval mode")
    return arguments


def _positive_integer(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if value <= 0 or str(value) != raw:
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    return value


def run_google_genai_audio_smoke(arguments: argparse.Namespace) -> dict[str, object]:
    """Run catalog discovery and one selected public audio workflow."""
    settings = GoogleGenAISettings()
    try:
        models = list_google_genai_models(settings, arguments.timeout)
    except OCRLLMError as error:
        raise _LiveSmokeFailure("catalog", error) from None
    except Exception:
        raise _LiveSmokeFailure("catalog", None) from None
    if arguments.model not in models:
        raise _LiveSmokeFailure(
            "model_selection",
            ConfigError(
                "The requested Google model is absent from the current catalog.",
                code="CONFIG_INVALID",
            ),
        ) from None
    try:
        config = Config(
            provider=settings,
            audio_model=AudioModelSettings(name=arguments.model),
            timeout_seconds=arguments.timeout,
            output_dir=arguments.output_dir,
            resume=arguments.resume,
        )
        if arguments.long:
            if arguments.interval_minutes is None:
                result = recognize_long_mp3(arguments.audio, config=config)
            else:
                result = recognize_long_mp3(
                    arguments.audio,
                    config=config,
                    interval_minutes=arguments.interval_minutes,
                )
        else:
            result = recognize(arguments.audio, config=config)
        recognition = _safe_recognition_summary(
            result,
            arguments.model,
            require_google_files=arguments.long,
            interval_minutes=arguments.interval_minutes,
            expected_output_dir=arguments.output_dir,
            resume=arguments.resume,
        )
    except OCRLLMError as error:
        raise _LiveSmokeFailure("recognition", error) from None
    except Exception:
        raise _LiveSmokeFailure("recognition", None) from None
    return {
        "status": "passed",
        "catalog_count": len(models),
        "model": arguments.model,
        "recognition": recognition,
    }


def _safe_recognition_summary(
    result: Any,
    model: str,
    *,
    require_google_files: bool = False,
    interval_minutes: int | None = None,
    expected_output_dir: Path | None = None,
    resume: bool = False,
) -> dict[str, object]:
    if (interval_minutes is None) != (expected_output_dir is None):
        raise ConfigError(
            "Google interval audio summary inputs are inconsistent.",
            code="CONFIG_INVALID",
        ) from None
    metadata = result.metadata
    if result.source_type != "audio":
        raise ConfigError(
            "Google audio live recognition returned an unexpected result boundary.",
            code="CONFIG_INVALID",
        ) from None
    output_path = result.output_path
    if interval_minutes is None:
        if output_path is not None:
            raise ConfigError(
                "Google audio live recognition returned an unexpected result boundary.",
                code="CONFIG_INVALID",
            ) from None
    elif (
        not isinstance(output_path, Path)
        or output_path.name != "result.md"
        or output_path.parent.parent != expected_output_dir
        or not output_path.is_file()
        or (output_path.parent / ".ocrllm-long-audio-resume.json").exists()
    ):
        raise ConfigError(
            "Google interval audio did not publish and clean temporary state.",
            code="CONFIG_INVALID",
        ) from None
    if metadata.get("provider") != "google" or metadata.get("model") != model:
        raise ConfigError(
            "Google audio live recognition returned an unexpected provider identity.",
            code="CONFIG_INVALID",
        ) from None
    call_count = metadata.get("provider_call_count")
    usage = metadata.get("current_model_token_usage", ())
    duration_seconds = metadata.get("duration_seconds")
    byte_size = metadata.get("byte_size")
    if (
        isinstance(duration_seconds, bool)
        or not isinstance(duration_seconds, (int, float))
        or not math.isfinite(float(duration_seconds))
        or duration_seconds <= 0
        or type(byte_size) is not int
        or byte_size <= 0
    ):
        raise ConfigError(
            "Google audio live recognition returned invalid source evidence.",
            code="CONFIG_INVALID",
        ) from None
    if require_google_files and (
        result.status != "complete"
        or metadata.get("transport") != "google_files"
        or metadata.get("remote_file_deleted") is not True
        or metadata.get("provider_client_closed") is not True
        or duration_seconds <= 300.0
    ):
        raise ConfigError(
            "Google long-audio live recognition did not complete its Files lifecycle.",
            code="CONFIG_INVALID",
        ) from None
    expected_calls = (
        1
        if interval_minutes is None
        else math.ceil(duration_seconds / (interval_minutes * 60))
    )
    if call_count != expected_calls or type(call_count) is not int:
        raise ConfigError(
            "Google audio live recognition returned an unexpected provider call count.",
            code="CONFIG_INVALID",
        ) from None
    current_run_calls = metadata.get("current_run_provider_call_count")
    if interval_minutes is not None and (
        type(current_run_calls) is not int
        or current_run_calls < 0
        or current_run_calls > expected_calls
        or (not resume and current_run_calls != expected_calls)
    ):
        raise ConfigError(
            "Google interval audio returned an unexpected current-run call count.",
            code="CONFIG_INVALID",
        ) from None
    if (
        type(usage) is not tuple
        or len(usage) != 1
        or not isinstance(usage[0], Mapping)
        or usage[0].get("model") != model
    ):
        raise ConfigError(
            "Google audio live recognition returned unexpected per-model usage.",
            code="CONFIG_INVALID",
        ) from None
    input_tokens = usage[0].get("input_tokens")
    output_tokens = usage[0].get("output_tokens")
    if not _is_optional_token_count(input_tokens) or not _is_optional_token_count(
        output_tokens
    ):
        raise ConfigError(
            "Google audio live recognition returned invalid token usage.",
            code="CONFIG_INVALID",
        ) from None
    summary = {
        "provider_call_count": call_count,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
    if require_google_files:
        summary["transport"] = "google_files"
        summary["remote_file_deleted"] = True
    if interval_minutes is not None:
        summary["current_run_provider_call_count"] = current_run_calls
        summary["interval_minutes"] = interval_minutes
        summary["result_published"] = True
        summary["resume"] = resume
    return summary


def _is_optional_token_count(value: object) -> bool:
    return value is None or (type(value) is int and value >= 0)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    try:
        summary = run_google_genai_audio_smoke(arguments)
    except _LiveSmokeFailure as failure:
        if failure.error is None:
            return _report_unexpected_failure(failure.stage)
        return _report_typed_failure(failure.error, failure.stage)
    except OCRLLMError as error:
        return _report_typed_failure(error, None)
    except Exception:
        return _report_unexpected_failure(None)
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


def _report_typed_failure(error: OCRLLMError, stage: str | None) -> int:
    scope = error.details.get("failure_scope")
    if scope is None and isinstance(error, ProviderError):
        scope = get_provider_error_disposition(error).scope
    cleanup = {
        name: error.details[name]
        for name in ("remote_file_deleted", "provider_client_closed")
        if type(error.details.get(name)) is bool
    }
    progress = {
        name: error.details[name]
        for name in ("provider_calls_attempted", "persisted_interval_count")
        if type(error.details.get(name)) is int and error.details[name] >= 0
    }
    operation = error.details.get("provider_operation")
    if operation not in {
        "client_setup",
        "catalog",
        "upload",
        "processing",
        "generation",
    }:
        operation = None
    return _report_failure(
        code=error.code,
        scope=scope,
        stage=stage,
        cleanup=cleanup or None,
        progress=progress or None,
        operation=operation,
    )


def _report_unexpected_failure(stage: str | None) -> int:
    return _report_failure(
        code="UNEXPECTED_SAFE_FAILURE",
        scope=None,
        stage=stage,
        cleanup=None,
        progress=None,
        operation=None,
    )


def _report_failure(
    *,
    code: str,
    scope: object,
    stage: str | None,
    cleanup: dict[str, bool] | None,
    progress: dict[str, int] | None,
    operation: str | None,
) -> int:
    summary: dict[str, object] = {
        "status": "failed",
        "error": {
            "code": code,
            "scope": scope,
            "stage": stage,
        },
    }
    if operation is not None:
        summary["error"]["operation"] = operation
    if cleanup is not None:
        summary["cleanup"] = cleanup
    if progress is not None:
        summary["progress"] = progress
    print(
        json.dumps(
            summary,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
