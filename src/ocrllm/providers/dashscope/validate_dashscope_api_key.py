"""Validate one explicit DashScope OpenAI-compatible credential."""

from __future__ import annotations

from ...errors import ConfigError


def validate_dashscope_api_key(api_key: object, *, field_name: str) -> str:
    """Return one exact safe-to-use key without ever echoing its value."""
    if (
        type(api_key) is not str
        or not api_key
        or api_key != api_key.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in api_key)
    ):
        raise ConfigError(
            f"{field_name} must be nonempty exact text.",
            code="CONFIG_INVALID",
        ) from None
    if api_key.startswith("sk-sp-"):
        raise ConfigError(
            "DashScope Coding Plan credentials cannot authorize this library adapter.",
            code="CONFIG_INVALID",
        ) from None
    return api_key
