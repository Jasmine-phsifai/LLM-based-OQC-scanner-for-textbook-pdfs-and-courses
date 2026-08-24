"""Immutable model identity for audio recognition."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import ConfigError


@dataclass(frozen=True, slots=True)
class AudioModelSettings:
    """Select one explicit audio model."""

    name: str | None = None

    def __post_init__(self) -> None:
        if self.name is not None and not _is_exact_model_text(self.name):
            raise ConfigError(
                "AudioModelSettings.name must be nonempty exact text when set.",
                code="CONFIG_INVALID",
            ) from None


def _is_exact_model_text(value: object) -> bool:
    return (
        type(value) is str
        and bool(value)
        and value == value.strip()
        and not any(ord(character) < 32 or ord(character) == 127 for character in value)
    )
