"""Run one scalar provider model through the existing image call boundary."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ..config import Config
from ..errors import ConfigError
from ..vision_model_settings import VisionModelSettings
from .call_vision_provider import call_vision_provider
from .openai_compatible.openai_compatible_provider import OpenAICompatibleProvider
from .openai_compatible.provider_settings import OpenAICompatibleSettings
from .provider_model import ProviderModel
from .resolve_vision_provider import resolve_vision_provider
from .resolved_vision_provider import ResolvedVisionProvider
from .vision_provider_response import VisionProviderResponse


def recognize_provider_model_images(
    provider_model: ProviderModel,
    image_paths: Sequence[Path],
    *,
    prompt: str,
    timeout_seconds: float = 120.0,
) -> str | VisionProviderResponse:
    """Dispatch one no-fallback image request through an existing adapter."""
    if type(provider_model) is not ProviderModel:
        raise ConfigError(
            "recognize_provider_model_images requires an exact ProviderModel.",
            code="CONFIG_INVALID",
            details={"provider_calls_attempted": 0},
        ) from None
    if not provider_model.supports_plain_ocr:
        raise ConfigError(
            "The selected ProviderModel does not support image OCR.",
            code="CONFIG_INVALID",
            details={"provider_calls_attempted": 0},
        ) from None
    if type(provider_model.settings) is OpenAICompatibleSettings:
        config = Config(timeout_seconds=timeout_seconds)
        resolved_provider = ResolvedVisionProvider(
            value=OpenAICompatibleProvider(
                vendor=provider_model.vendor,
                model=provider_model.model,
                settings=provider_model.settings,
            ),
            name=provider_model.vendor,
            model=provider_model.model,
            built_in=True,
        )
    else:
        config = Config(
            provider=provider_model.settings,
            vision_model=VisionModelSettings(name=provider_model.model),
            timeout_seconds=timeout_seconds,
        )
        resolved_provider = resolve_vision_provider(config)
    return call_vision_provider(
        resolved_provider,
        image_paths,
        prompt=prompt,
        config=config,
    )
