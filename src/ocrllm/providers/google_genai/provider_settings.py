"""Secret-safe settings for the native Google GenAI provider."""

from __future__ import annotations

from dataclasses import dataclass, field

from ...errors import ConfigError


@dataclass(frozen=True, slots=True)
class GoogleGenAISettings:
    """Select Google GenAI while keeping its optional credential private."""

    api_key: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.api_key is not None:
            _validate_google_api_key(
                self.api_key,
                field_name="GoogleGenAISettings.api_key",
            )


def _validate_google_api_key(value: object, *, field_name: str) -> str:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or any(
            character.isspace()
            or ord(character) < 32
            or ord(character) == 127
            for character in value
        )
    ):
        raise ConfigError(
            f"{field_name} must be nonempty exact credential text.",
            code="CONFIG_INVALID",
        ) from None
    return value
