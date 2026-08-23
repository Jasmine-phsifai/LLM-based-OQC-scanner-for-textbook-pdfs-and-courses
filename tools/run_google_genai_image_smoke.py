"""Run the bounded, credential-safe Google GenAI image live gate."""

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
from ocrllm.errors import ConfigError, OCRLLMError, ProviderError


_INVALID_LIVE_GATE_KEY = "ocrllm-intentionally-invalid-live-smoke-key"
_CREDENTIAL_FAILURE_CODES = frozenset(
    {"PROVIDER_AUTHENTICATION", "PROVIDER_PERMISSION_DENIED"}
)


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse one explicit one-image plus eight-image live request."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--single-image", required=True, type=Path)
    parser.add_argument(
        "--group-image",
        required=True,
        type=Path,
        nargs=8,
        metavar="IMAGE",
        help="exactly eight explicit image paths",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    return parser.parse_args(argv)


def run_google_genai_image_smoke(arguments: argparse.Namespace) -> dict[str, object]:
    """Run catalog, one-image, eight-image, and bad-credential checks once."""
    settings = GoogleGenAISettings()
    models = list_google_genai_models(settings, arguments.timeout)
    if arguments.model not in models:
        raise ConfigError(
            "The requested Google model is absent from the current catalog.",
            code="CONFIG_INVALID",
        ) from None

    config = Config(
        provider=settings,
        vision_model=VisionModelSettings(name=arguments.model),
        timeout_seconds=arguments.timeout,
    )
    single_result = recognize(arguments.single_image, config=config)
    group_result = recognize(tuple(arguments.group_image), config=config)

    invalid_error = _require_invalid_credential_failure(arguments.timeout)
    return {
        "status": "passed",
        "catalog_count": len(models),
        "model": arguments.model,
        "single": _safe_recognition_summary(single_result, arguments.model),
        "group": _safe_recognition_summary(group_result, arguments.model),
        "invalid_credential": invalid_error,
    }


def _require_invalid_credential_failure(timeout_seconds: float) -> dict[str, str]:
    try:
        list_google_genai_models(
            GoogleGenAISettings(api_key=_INVALID_LIVE_GATE_KEY),
            timeout_seconds,
        )
    except ProviderError as error:
        scope = error.details.get("failure_scope")
        if error.code not in _CREDENTIAL_FAILURE_CODES or scope != "credential":
            raise ConfigError(
                "The invalid-credential probe did not return a credential failure.",
                code="CONFIG_INVALID",
            ) from None
        return {"code": error.code, "scope": scope}
    raise ConfigError(
        "The invalid-credential probe unexpectedly succeeded.",
        code="CONFIG_INVALID",
    ) from None


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


def _safe_failure_summary(error: OCRLLMError) -> dict[str, object]:
    return {
        "status": "failed",
        "error": {
            "code": error.code,
            "scope": error.details.get("failure_scope"),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    try:
        summary = run_google_genai_image_smoke(arguments)
    except OCRLLMError as error:
        summary = _safe_failure_summary(error)
        print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
        return 1
    except Exception:
        print(
            json.dumps(
                {"status": "failed", "error": {"code": "UNEXPECTED_SAFE_FAILURE"}},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 1
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
