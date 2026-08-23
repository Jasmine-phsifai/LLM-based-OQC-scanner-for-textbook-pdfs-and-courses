"""Resolve an injected object or one exact built-in vision provider."""

from __future__ import annotations

import importlib

from ..config import Config
from ..errors import ConfigError
from .dashscope.provider_settings import DashScopeSettings
from .dashscope.resolve_dashscope_model import resolve_dashscope_model
from .google_genai.provider_settings import GoogleGenAISettings
from .resolved_vision_provider import ResolvedVisionProvider


def resolve_vision_provider(config: Config) -> ResolvedVisionProvider:
    """Return one explicit vision provider without initiating external work."""
    provider = config.provider
    if provider is None:
        raise ConfigError(
            "Image recognition requires an explicit Config.provider.",
            code="CONFIG_MISSING",
        ) from None

    if type(provider) is DashScopeSettings:
        provider_module = importlib.import_module(
            ".dashscope.recognize_images",
            package=__package__,
        )
        return ResolvedVisionProvider(
            value=provider_module,
            name="dashscope",
            model=resolve_dashscope_model(
                config.vision_model.name,
                settings=provider,
            ),
            built_in=True,
        )

    if type(provider) is GoogleGenAISettings:
        model = config.vision_model.name
        if type(model) is not str or not model:
            raise ConfigError(
                "Google GenAI image recognition requires an explicit model.",
                code="CONFIG_MISSING",
            ) from None
        provider_module = importlib.import_module(
            ".google_genai.recognize_images",
            package=__package__,
        )
        return ResolvedVisionProvider(
            value=provider_module,
            name="google",
            model=model,
            built_in=True,
        )

    return ResolvedVisionProvider(
        value=provider,
        name=None,
        model=config.vision_model.name,
        built_in=False,
    )
