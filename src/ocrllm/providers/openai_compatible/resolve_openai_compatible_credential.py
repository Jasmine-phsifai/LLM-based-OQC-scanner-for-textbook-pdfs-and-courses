"""Resolve one OpenAI-compatible credential without exposing it."""

from __future__ import annotations

import os

from ...errors import ConfigError
from .provider_settings import OpenAICompatibleSettings, _validate_secret


_UNAUTHENTICATED_CLIENT_PLACEHOLDER = "ocrllm-no-api-key"


def resolve_openai_compatible_credential(
    settings: OpenAICompatibleSettings,
) -> str:
    """Return the explicit/environment credential or a local placeholder."""
    if type(settings) is not OpenAICompatibleSettings:
        raise ConfigError(
            "OpenAI-compatible dispatch requires exact adapter settings.",
            code="CONFIG_INVALID",
        ) from None
    api_key = settings.api_key
    if api_key is None and settings.api_key_env is not None:
        api_key = os.environ.get(settings.api_key_env)
    if api_key is None:
        return _UNAUTHENTICATED_CLIENT_PLACEHOLDER
    _validate_secret(api_key)
    return api_key
