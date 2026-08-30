"""Validate one scalar image task and select its internal prompt."""

from __future__ import annotations

from .errors import ConfigError
from .profiles.build_board_prompt import BOARD_PROMPT_VERSION, build_board_prompt
from .profiles.build_plain_ocr_prompt import (
    PLAIN_OCR_PROMPT_VERSION,
    build_plain_ocr_prompt,
)
from .providers.provider_model import ProviderModel


def resolve_merged_image_prompt(
    provider: ProviderModel,
    image_task: str,
) -> tuple[str, str]:
    """Return the fixed prompt/version after complete scalar capability preflight."""
    if type(provider) is not ProviderModel:
        raise ConfigError(
            "Merged-image provider must be an exact ProviderModel.",
            code="CONFIG_INVALID",
            details={"provider_calls_attempted": 0},
        ) from None
    if type(image_task) is not str or image_task not in {"plain_ocr", "detail_ocr"}:
        raise ConfigError(
            "image_task must be exactly 'plain_ocr' or 'detail_ocr'.",
            code="CONFIG_INVALID",
            details={"provider_calls_attempted": 0},
        ) from None
    supported = (
        provider.supports_plain_ocr
        if image_task == "plain_ocr"
        else provider.supports_detail_ocr
    )
    if not supported:
        raise ConfigError(
            "The selected ProviderModel does not support the requested image task.",
            code="CONFIG_INVALID",
            details={
                "image_task": image_task,
                "model": provider.model,
                "provider": provider.vendor,
                "provider_calls_attempted": 0,
            },
        ) from None
    if image_task == "plain_ocr":
        return build_plain_ocr_prompt(), PLAIN_OCR_PROMPT_VERSION
    return build_board_prompt(), BOARD_PROMPT_VERSION
