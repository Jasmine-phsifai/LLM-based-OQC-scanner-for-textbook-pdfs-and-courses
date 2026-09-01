"""Secret-safe routing settings for OpenAI-compatible Chat Completions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from ...errors import ConfigError


_ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True, kw_only=True)
class OpenAICompatibleSettings:
    """Configure one compatible endpoint without asserting vendor behavior."""

    base_url: str
    api_key_env: str | None = None
    api_key: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        _validate_base_url(self.base_url)
        if self.api_key_env is not None and (
            type(self.api_key_env) is not str
            or _ENVIRONMENT_NAME.fullmatch(self.api_key_env) is None
        ):
            raise ConfigError(
                "OpenAICompatibleSettings.api_key_env must be an environment "
                "variable name when set.",
                code="CONFIG_INVALID",
            ) from None
        if self.api_key is not None:
            _validate_secret(self.api_key)


def _validate_base_url(value: object) -> None:
    if type(value) is not str or not value or value != value.strip():
        _raise_invalid_base_url()
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        _raise_invalid_base_url()
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except (TypeError, ValueError):
        _raise_invalid_base_url()
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or port is not None
        and not 1 <= port <= 65535
    ):
        _raise_invalid_base_url()


def _raise_invalid_base_url() -> None:
    raise ConfigError(
        "OpenAICompatibleSettings.base_url must be an absolute HTTP(S) endpoint "
        "without credentials, query, or fragment.",
        code="CONFIG_INVALID",
    ) from None


def _validate_secret(value: object) -> None:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ConfigError(
            "OpenAICompatibleSettings.api_key must be nonempty exact text.",
            code="CONFIG_INVALID",
        ) from None
