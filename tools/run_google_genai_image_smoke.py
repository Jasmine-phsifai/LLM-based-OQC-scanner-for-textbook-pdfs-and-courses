"""Run one bounded, credential-safe Google GenAI image live smoke."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ocrllm import (
    Config,
    GoogleGenAISettings,
    VisionModelSettings,
    recognize,
)
from ocrllm.errors import ConfigError, OCRLLMError


class _LiveSmokeFailure(Exception):
    """Keep a runner stage beside, not inside, a public product error."""

    def __init__(self, stage: str, error: OCRLLMError | None) -> None:
        self.stage = stage
        self.error = error
        super().__init__(stage)


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse one explicit model, image path, and timeout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=120.0)
    return parser.parse_args(argv)


def run_google_genai_image_smoke(arguments: argparse.Namespace) -> dict[str, object]:
    """Run one public image recognition with adapter-owned catalog validation."""
    settings = GoogleGenAISettings()
    try:
        result = recognize(
            arguments.image,
            config=Config(
                provider=settings,
                vision_model=VisionModelSettings(name=arguments.model),
                timeout_seconds=arguments.timeout,
            ),
        )
        recognition = _safe_recognition_summary(result, arguments.model)
    except OCRLLMError as error:
        raise _LiveSmokeFailure("recognition", error) from None
    except Exception:
        raise _LiveSmokeFailure("recognition", None) from None
    return {
        "status": "passed",
        "model": arguments.model,
        "recognition": recognition,
    }


def _safe_recognition_summary(result: Any, model: str) -> dict[str, object]:
    metadata = result.metadata
    if metadata.get("provider") != "google" or metadata.get("model") != model:
        raise ConfigError(
            "Google live recognition returned an unexpected provider identity.",
            code="CONFIG_INVALID",
        ) from None
    provider_call_count = metadata.get("provider_call_count")
    if type(provider_call_count) is not int or provider_call_count != 1:
        raise ConfigError(
            "Google live recognition did not report exactly one provider call.",
            code="CONFIG_INVALID",
        ) from None
    usage = metadata.get("current_model_token_usage", ())
    if (
        type(usage) is not tuple
        or len(usage) != 1
        or not isinstance(usage[0], Mapping)
        or usage[0].get("model") != model
    ):
        raise ConfigError(
            "Google live recognition returned unexpected per-model usage.",
            code="CONFIG_INVALID",
        ) from None
    input_tokens = usage[0].get("input_tokens")
    output_tokens = usage[0].get("output_tokens")
    if not _is_optional_token_count(input_tokens) or not _is_optional_token_count(
        output_tokens
    ):
        raise ConfigError(
            "Google live recognition returned invalid token usage.",
            code="CONFIG_INVALID",
        ) from None
    return {
        "provider_call_count": provider_call_count,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def _is_optional_token_count(value: object) -> bool:
    return value is None or (type(value) is int and value >= 0)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    try:
        summary = run_google_genai_image_smoke(arguments)
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
    operation = error.details.get("provider_operation")
    if operation not in {"client_setup", "catalog", "generation"}:
        operation = None
    return _report_failure(
        code=error.code,
        scope=error.details.get("failure_scope"),
        stage=stage,
        http_status=error.details.get("http_status"),
        provider_status=error.details.get("provider_status"),
        provider_calls_attempted=error.details.get("provider_calls_attempted"),
        operation=operation,
    )


def _report_unexpected_failure(stage: str | None) -> int:
    return _report_failure(
        code="UNEXPECTED_SAFE_FAILURE",
        scope=None,
        stage=stage,
    )


def _report_failure(
    *,
    code: str,
    scope: object,
    stage: str | None,
    http_status: object = None,
    provider_status: object = None,
    provider_calls_attempted: object = None,
    operation: str | None = None,
) -> int:
    error_summary = {
        "code": code,
        "scope": scope,
        "stage": stage,
    }
    if type(http_status) is int and 100 <= http_status <= 599:
        error_summary["http_status"] = http_status
    if (
        type(provider_status) is str
        and provider_status.isascii()
        and len(provider_status) <= 128
        and provider_status.replace("_", "").isalnum()
    ):
        error_summary["provider_status"] = provider_status
    if operation is not None:
        error_summary["operation"] = operation
    summary: dict[str, object] = {
        "status": "failed",
        "error": error_summary,
    }
    if type(provider_calls_attempted) is int and provider_calls_attempted >= 0:
        summary["progress"] = {
            "provider_calls_attempted": provider_calls_attempted,
        }
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
