"""Validate the optional public long-audio interval selector."""

from __future__ import annotations

from .config import Config
from .errors import ConfigError


def validate_long_audio_interval_minutes(
    interval_minutes: object,
    *,
    config: Config,
) -> int | None:
    """Return whole mode or one exact positive integer interval."""
    if interval_minutes is None:
        return None
    if type(interval_minutes) is not int or interval_minutes <= 0:
        raise ConfigError(
            "Long-audio interval_minutes must be a positive integer.",
            code="CONFIG_INVALID",
        ) from None
    if config.output_dir is None:
        raise ConfigError(
            "Long-audio interval recognition requires Config.output_dir.",
            code="CONFIG_INVALID",
        ) from None
    return interval_minutes
