"""Validate shared options for direct Google MP3 recognition."""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .errors import ConfigError, InvalidSource


def validate_google_mp3_options(
    source_paths: tuple[Path, ...],
    *,
    config: Config,
) -> None:
    """Reject groups, persistence, or incomplete Google audio configuration."""
    from .providers.google_genai.provider_settings import GoogleGenAISettings

    if len(source_paths) != 1:
        raise InvalidSource(
            "Direct Google MP3 recognition accepts exactly one source.",
            code="SOURCE_INVALID",
        ) from None
    if config.output_dir is not None or config.resume or config.overwrite:
        raise ConfigError(
            "Direct Google MP3 recognition is currently in-memory only.",
            code="CONFIG_INVALID",
        ) from None
    if type(config.provider) is not GoogleGenAISettings:
        raise ConfigError(
            "Direct Google MP3 recognition requires GoogleGenAISettings.",
            code="CONFIG_INVALID",
        ) from None
    if type(config.audio_model.name) is not str or not config.audio_model.name:
        raise ConfigError(
            "Direct Google MP3 recognition requires an explicit audio model.",
            code="CONFIG_MISSING",
        ) from None
