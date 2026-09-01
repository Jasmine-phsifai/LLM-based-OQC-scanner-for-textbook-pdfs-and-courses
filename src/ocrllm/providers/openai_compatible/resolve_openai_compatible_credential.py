"""Resolve one OpenAI-compatible credential without exposing it."""

from __future__ import annotations

import os

from ...errors import ConfigError
from .provider_settings import OpenAICompatibleSettings, _validate_secret


def resolve_openai_compatible_credential(
    settings: OpenAICompatibleSettings,
) -> str:
    """Return the explicit or configured-environment credential."""
    if type(settings) is not OpenAICompatibleSettings:
        raise ConfigError(
            "OpenAI-compatible dispatch requires exact adapter settings.",
            code="CONFIG_INVALID",
        ) from None
    api_key = settings.api_key
    if api_key is None:
        api_key = os.environ.get(settings.api_key_env)
    if api_key is None:
        raise ConfigError(
            f"OpenAI-compatible dispatch requires {settings.api_key_env} or an "
            "explicit api_key.",
            code="CONFIG_MISSING",
            details={"provider_calls_attempted": 0},
        ) from None
    _validate_secret(api_key)
    return api_key
