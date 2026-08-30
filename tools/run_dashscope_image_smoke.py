"""Run one bounded, credential-safe DashScope image live smoke."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ocrllm import Config, DashScopeSettings, VisionModelSettings, recognize
from ocrllm.errors import ConfigError, OCRLLMError, ProviderError
from ocrllm.provider_error_disposition import get_provider_error_disposition
from ocrllm.profiles.build_board_prompt import build_board_prompt
from ocrllm.providers.dashscope.resolve_dashscope_model import (
    fetch_dashscope_model_catalog,
)
from ocrllm.providers.provider_model import ProviderModel
from ocrllm.providers.recognize_provider_model_images import (
    recognize_provider_model_images,
)
from ocrllm.providers.vision_provider_response import VisionProviderResponse


class _LiveSmokeFailure(Exception):
    """Keep one safe runner stage beside a public product error."""

    def __init__(self, stage: str, error: OCRLLMError | None) -> None:
        self.stage = stage
        self.error = error
        super().__init__(stage)


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse one explicit current model, image path, and timeout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--provider-model",
        action="store_true",
        help="Exercise the private scalar ProviderModel consumer.",
    )
    return parser.parse_args(argv)


def run_dashscope_image_smoke(arguments: argparse.Namespace) -> dict[str, object]:
    """Discover the Beijing catalog and perform at most one recognition call."""
    settings = DashScopeSettings.for_region("cn-beijing")
    try:
        models = fetch_dashscope_model_catalog(settings)
    except OCRLLMError as error:
        raise _LiveSmokeFailure("catalog", error) from None
    except Exception:
        raise _LiveSmokeFailure("catalog", None) from None
    if models is None:
        raise _LiveSmokeFailure(
            "catalog",
            ProviderError(
                "The DashScope model catalog is temporarily unavailable.",
                code="PROVIDER_CATALOG_UNAVAILABLE",
                retryable=True,
                details={"provider": "dashscope"},
            ),
        ) from None
    if arguments.model not in models:
        raise _LiveSmokeFailure(
            "model_selection",
            ConfigError(
                "The requested DashScope model is absent from the current catalog.",
                code="CONFIG_INVALID",
            ),
        ) from None

    try:
        if arguments.provider_model:
            provider_model = ProviderModel(
                vendor="dashscope",
                model=arguments.model,
                adapter_id="dashscope_openai_compatible",
                settings=settings,
            )
            response = recognize_provider_model_images(
                provider_model,
                (arguments.image,),
                prompt=build_board_prompt(),
                timeout_seconds=arguments.timeout,
            )
            recognition = _safe_provider_model_summary(response, arguments.model)
        else:
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
    summary = {
        "status": "passed",
        "catalog_count": len(models),
        "model": arguments.model,
        "recognition": recognition,
    }
    if arguments.provider_model:
        summary["runtime_path"] = "provider_model"
    return summary


def _safe_provider_model_summary(
    response: str | VisionProviderResponse,
    model: str,
) -> dict[str, object]:
    """Validate one no-retry entity response without exposing its content."""
    if (
        type(response) is not VisionProviderResponse
        or response.client_closed is not True
    ):
        raise ConfigError(
            "The ProviderModel live request returned incomplete success evidence.",
            code="CONFIG_INVALID",
        ) from None
    return {
        "provider_call_count": 1,
        "model": model,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "client_closed": True,
    }


def _safe_recognition_summary(result: Any, model: str) -> dict[str, object]:
    """Validate one-call evidence without exposing recognized content."""
    metadata = result.metadata
    if (
        result.status != "complete"
        or metadata.get("provider") != "dashscope"
        or metadata.get("model") != model
        or metadata.get("provider_region") != "cn-beijing"
    ):
        raise ConfigError(
            "DashScope live recognition returned an unexpected result identity.",
            code="CONFIG_INVALID",
        ) from None
    provider_call_count = metadata.get("provider_call_count")
    if type(provider_call_count) is not int or provider_call_count != 1:
        raise ConfigError(
            "DashScope live recognition did not report exactly one provider call.",
            code="CONFIG_INVALID",
        ) from None
    _require_one_successful_attempt(metadata.get("model_attempts"), model=model)
    _require_one_draft_slot(metadata.get("workflow_slots"), model=model)
    if metadata.get("provider_client_closed", True) is not True:
        raise ConfigError(
            "DashScope live recognition did not close its provider client.",
            code="CONFIG_INVALID",
        ) from None
    input_tokens, output_tokens = _require_model_usage(
        metadata.get("current_model_token_usage"),
        model=model,
    )
    return {
        "provider_call_count": provider_call_count,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "client_closed": True,
    }


def _require_one_successful_attempt(value: object, *, model: str) -> None:
    if type(value) is not tuple or len(value) != 1 or not isinstance(value[0], Mapping):
        raise _invalid_attempt_evidence()
    attempt = value[0]
    if (
        attempt.get("model") != model
        or attempt.get("outcome") != "success"
        or attempt.get("provider_calls_attempted") != 1
    ):
        raise _invalid_attempt_evidence()


def _require_one_draft_slot(value: object, *, model: str) -> None:
    if type(value) is not tuple or len(value) != 1 or not isinstance(value[0], Mapping):
        raise _invalid_attempt_evidence()
    slot = value[0]
    if (
        slot.get("slot_id") != "draft"
        or slot.get("workflow_pass") != "draft"
        or slot.get("provider") != "dashscope"
        or slot.get("model") != model
        or slot.get("reused") is not False
        or slot.get("provider_calls_attempted") != 1
    ):
        raise _invalid_attempt_evidence()


def _require_model_usage(
    value: object,
    *,
    model: str,
) -> tuple[int | None, int | None]:
    if type(value) is not tuple or len(value) != 1 or not isinstance(value[0], Mapping):
        raise _invalid_attempt_evidence()
    usage = value[0]
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if (
        usage.get("model") != model
        or not _is_optional_token_count(input_tokens)
        or not _is_optional_token_count(output_tokens)
    ):
        raise _invalid_attempt_evidence()
    return input_tokens, output_tokens


def _is_optional_token_count(value: object) -> bool:
    return value is None or (type(value) is int and value >= 0)


def _invalid_attempt_evidence() -> ConfigError:
    return ConfigError(
        "DashScope live recognition returned unexpected attempt evidence.",
        code="CONFIG_INVALID",
    )


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    try:
        summary = run_dashscope_image_smoke(arguments)
    except _LiveSmokeFailure as failure:
        if failure.error is None:
            return _report_failure(
                code="UNEXPECTED_SAFE_FAILURE",
                scope=None,
                stage=failure.stage,
            )
        return _report_failure(
            code=failure.error.code,
            scope=_safe_failure_scope(failure.error),
            stage=failure.stage,
        )
    except OCRLLMError as error:
        return _report_failure(
            code=error.code,
            scope=_safe_failure_scope(error),
            stage=None,
        )
    except Exception:
        return _report_failure(
            code="UNEXPECTED_SAFE_FAILURE",
            scope=None,
            stage=None,
        )
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


def _safe_failure_scope(error: OCRLLMError) -> str | None:
    """Report an explicit scope or the existing canonical provider default."""
    if not isinstance(error, ProviderError):
        return None
    return get_provider_error_disposition(error).scope


def _report_failure(*, code: str, scope: object, stage: str | None) -> int:
    print(
        json.dumps(
            {
                "status": "failed",
                "error": {"code": code, "scope": scope, "stage": stage},
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
