"""Validate public options for one short-audio recognition request."""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .errors import ConfigError, InvalidSource


def validate_short_audio_options(
    source_paths: tuple[Path, ...],
    *,
    config: Config,
) -> None:
    """Reject unsupported short-audio source and configuration combinations."""
    from .providers.google_genai.provider_settings import GoogleGenAISettings

    if len(source_paths) != 1:
        raise InvalidSource(
            "Short-audio recognition accepts exactly one MP3 source.",
            code="SOURCE_INVALID",
        ) from None
    if config.output_dir is not None or config.resume or config.overwrite:
        raise ConfigError(
            "Short-audio recognition is currently in-memory only.",
            code="CONFIG_INVALID",
        ) from None
    if type(config.provider) is not GoogleGenAISettings:
        raise ConfigError(
            "Short-audio recognition requires GoogleGenAISettings.",
            code="CONFIG_INVALID",
        ) from None
    if type(config.audio_model.name) is not str or not config.audio_model.name:
        raise ConfigError(
            "Short-audio recognition requires an explicit audio model.",
            code="CONFIG_MISSING",
        ) from None
