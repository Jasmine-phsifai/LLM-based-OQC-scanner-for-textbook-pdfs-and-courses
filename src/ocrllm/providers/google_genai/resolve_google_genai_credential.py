"""Resolve one native Google credential without exposing it."""

from __future__ import annotations

import os

from ...errors import ConfigError
from .provider_settings import GoogleGenAISettings, _validate_google_api_key


def resolve_google_genai_credential(settings: GoogleGenAISettings) -> str:
    """Prefer explicit, then GOOGLE_API_KEY, then GEMINI_API_KEY."""
    if type(settings) is not GoogleGenAISettings:
        raise ConfigError(
            "Google credential resolution requires exact GoogleGenAISettings.",
            code="CONFIG_INVALID",
        ) from None
    if settings.api_key is not None:
        return settings.api_key
    for environment_name in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
        value = os.environ.get(environment_name)
        if value:
            return _validate_google_api_key(value, field_name=environment_name)
    raise ConfigError(
        "Google GenAI requires GoogleGenAISettings.api_key, GOOGLE_API_KEY, or GEMINI_API_KEY.",
        code="CONFIG_MISSING",
    ) from None
