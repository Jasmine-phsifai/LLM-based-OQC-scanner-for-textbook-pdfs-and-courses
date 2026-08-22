"""Resolve exactly one DashScope credential without exposing its value."""

from __future__ import annotations

import os

from ...errors import ConfigError
from .provider_settings import DashScopeSettings
from .validate_dashscope_api_key import validate_dashscope_api_key


def resolve_dashscope_credential(settings: DashScopeSettings) -> str:
    """Use the explicit key, then ``DASHSCOPE_API_KEY``, or fail safely."""
    if type(settings) is not DashScopeSettings:
        raise ConfigError(
            "DashScope credential resolution requires exact DashScopeSettings.",
            code="CONFIG_INVALID",
        ) from None
    if settings.credential_pool is not None:
        raise ConfigError(
            "Pooled DashScope credentials require a credential lease.",
            code="CONFIG_INVALID",
        ) from None
    api_key = settings.api_key
    if api_key is None:
        api_key = os.environ.get("DASHSCOPE_API_KEY")
    if api_key is None or api_key == "":
        raise ConfigError(
            "DashScope requires DashScopeSettings.api_key or DASHSCOPE_API_KEY.",
            code="CONFIG_MISSING",
        ) from None
    return validate_dashscope_api_key(
        api_key,
        field_name=(
            "DashScopeSettings.api_key"
            if settings.api_key is not None
            else "DASHSCOPE_API_KEY"
        ),
    )
