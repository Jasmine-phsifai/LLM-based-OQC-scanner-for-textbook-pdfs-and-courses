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
)
from ocrllm.errors import ConfigError, OCRLLMError, ProviderError


_INVALID_LIVE_GATE_KEY = "ocrllm-intentionally-invalid-audio-live-smoke-key"
_CREDENTIAL_FAILURE_CODES = frozenset(
    {"PROVIDER_AUTHENTICATION", "PROVIDER_PERMISSION_DENIED"}
)


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse one explicit model, MP3 path, and timeout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=120.0)
    return parser.parse_args(argv)


def run_google_genai_audio_smoke(arguments: argparse.Namespace) -> dict[str, object]:
    """Run catalog, one short-MP3 call, and bad-credential checks once."""
    settings = GoogleGenAISettings()
    models = list_google_genai_models(settings, arguments.timeout)
    if arguments.model not in models:
        raise ConfigError(
            "The requested Google model is absent from the current catalog.",
            code="CONFIG_INVALID",
        ) from None
    result = recognize(
        arguments.audio,
        config=Config(
            provider=settings,
            audio_model=AudioModelSettings(name=arguments.model),
            timeout_seconds=arguments.timeout,
        ),
    )
    return {
        "status": "passed",
        "catalog_count": len(models),
        "model": arguments.model,
        "recognition": _safe_recognition_summary(result, arguments.model),
        "invalid_credential": _require_invalid_credential_failure(arguments.timeout),
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
    return {
        "provider_call_count": call_count,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def _is_optional_token_count(value: object) -> bool:
    return value is None or (type(value) is int and value >= 0)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    try:
        summary = run_google_genai_audio_smoke(arguments)
    except OCRLLMError as error:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": {
                        "code": error.code,
                        "scope": error.details.get("failure_scope"),
                    },
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
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
