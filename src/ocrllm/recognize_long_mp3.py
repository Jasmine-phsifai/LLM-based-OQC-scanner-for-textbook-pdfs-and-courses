"""Public standalone recognition for one long MP3 through Google Files."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .config import Config
from .errors import InvalidSource, OCRLLMError
from .result import RecognitionResult


def recognize_long_mp3(
    source: str | Path | Sequence[str | Path],
    *,
    config: Config | None = None,
    interval_minutes: int | None = None,
) -> RecognitionResult:
    """Recognize one MP3 longer than five minutes without video integration."""
    from .clear_public_error import clear_public_error

    public_error: OCRLLMError | None = None
    try:
        return _recognize_long_mp3(
            source,
            config=config,
            interval_minutes=interval_minutes,
        )
    except OCRLLMError as error:
        public_error = error
    clear_public_error(public_error)
    raise public_error from None


def _recognize_long_mp3(
    source: str | Path | Sequence[str | Path],
    *,
    config: Config | None,
    interval_minutes: int | None,
) -> RecognitionResult:
    from .build_recognition_result import build_recognition_result
    from .coerce_source_paths import coerce_source_paths
    from .processors.recognize_long_mp3 import recognize_validated_long_mp3
    from .providers.provider_request_start_gate import (
        reuse_or_create_provider_request_start_gate,
    )
    from .validate_config import validate_config
    from .validate_google_mp3_options import validate_google_mp3_options
    from .validate_long_audio_interval_minutes import (
        validate_long_audio_interval_minutes,
    )
    from .validate_same_type_group import validate_same_type_group

    cfg = validate_config(config)
    source_paths = coerce_source_paths(source)
    if validate_same_type_group(source_paths) != "audio":
        raise InvalidSource(
            "recognize_long_mp3() requires one MP3 source.",
            code="SOURCE_INVALID",
        ) from None
    validate_google_mp3_options(
        source_paths,
        config=cfg,
        allow_persistence=True,
    )
    validated_interval = validate_long_audio_interval_minutes(
        interval_minutes,
        config=cfg,
    )
    with reuse_or_create_provider_request_start_gate(
        cfg.execution.provider_request_start_interval_seconds
    ):
        processor_output, output_path = recognize_validated_long_mp3(
            source_paths[0],
            config=cfg,
            interval_minutes=validated_interval,
        )
    return build_recognition_result(processor_output, output_path=output_path)
