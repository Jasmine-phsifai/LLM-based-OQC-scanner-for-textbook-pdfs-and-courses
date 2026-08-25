"""Run one bounded, credential-safe Google GenAI short-audio live gate."""

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
    return parser.parse_args(argv)


def run_google_genai_audio_smoke(arguments: argparse.Namespace) -> dict[str, object]:
    """Run current catalog discovery and one short-MP3 recognition call."""
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
        recognize_audio = recognize_long_mp3 if arguments.long else recognize
        result = recognize_audio(
            arguments.audio,
            config=Config(
                provider=settings,
                audio_model=AudioModelSettings(name=arguments.model),
                timeout_seconds=arguments.timeout,
            ),
        )
        recognition = _safe_recognition_summary(
            result,
            arguments.model,
            require_google_files=arguments.long,
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
) -> dict[str, object]:
    metadata = result.metadata
    if result.source_type != "audio" or result.output_path is not None:
        raise ConfigError(
            "Google audio live recognition returned an unexpected result boundary.",
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
    if call_count != 1 or type(call_count) is not int:
        raise ConfigError(
            "Google audio live recognition did not report exactly one provider call.",
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
    return _report_failure(
        code=error.code,
        scope=scope,
        stage=stage,
        cleanup=cleanup or None,
    )


def _report_unexpected_failure(stage: str | None) -> int:
    return _report_failure(
        code="UNEXPECTED_SAFE_FAILURE",
        scope=None,
        stage=stage,
        cleanup=None,
    )


def _report_failure(
    *,
    code: str,
    scope: object,
    stage: str | None,
    cleanup: dict[str, bool] | None,
) -> int:
    summary: dict[str, object] = {
        "status": "failed",
        "error": {
            "code": code,
            "scope": scope,
            "stage": stage,
        },
    }
    if cleanup is not None:
        summary["cleanup"] = cleanup
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
