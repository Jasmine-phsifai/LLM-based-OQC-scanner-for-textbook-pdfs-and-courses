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
    list_google_genai_models,
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
    """Run current catalog discovery and one image recognition call."""
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
        "catalog_count": len(models),
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
    return _report_failure(
        code=error.code,
        scope=error.details.get("failure_scope"),
        stage=stage,
    )


def _report_unexpected_failure(stage: str | None) -> int:
    return _report_failure(
        code="UNEXPECTED_SAFE_FAILURE",
        scope=None,
        stage=stage,
    )


def _report_failure(*, code: str, scope: object, stage: str | None) -> int:
    print(
        json.dumps(
            {
                "status": "failed",
                "error": {
                    "code": code,
                    "scope": scope,
                    "stage": stage,
                },
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
