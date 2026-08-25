"""Validate deterministic image-provider requirements before media work."""

from __future__ import annotations

from ..config import Config
from ..errors import ConfigError
from .dashscope.provider_settings import DashScopeSettings
from .google_genai.provider_settings import GoogleGenAISettings


def validate_vision_provider_config(
    config: Config,
    *,
    require_injected_callable: bool = False,
) -> None:
    """Reject a locally invalid vision route without provider or file access."""
    if config.image_mode == "ocr":
        return
    if config.provider is None:
        raise ConfigError(
            "Image recognition requires an explicit Config.provider.",
            code="CONFIG_MISSING",
        ) from None
    if type(config.provider) is GoogleGenAISettings:
        model = config.vision_model.name
        if type(model) is not str or not model:
            raise ConfigError(
                "Google GenAI image recognition requires an explicit model.",
                code="CONFIG_MISSING",
            ) from None
        return
    if type(config.provider) is DashScopeSettings:
        return
    if not require_injected_callable:
        return

    try:
        recognize_method = getattr(config.provider, "recognize_images", None)
    except Exception:
        raise ConfigError(
            "Config.provider recognize_images could not be inspected safely.",
            code="CONFIG_INVALID",
        ) from None
    if not callable(recognize_method):
        raise ConfigError(
            "Config.provider must be an injected object with a callable "
            "recognize_images method.",
            code="CONFIG_INVALID",
        ) from None
