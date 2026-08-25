"""Recognize retained video frames and audio through separate configurations."""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .video_recognition_outcome import VideoRecognitionOutcome


def recognize_video(
    source: str | Path,
    *,
    output_dir: str | Path,
    image_config: Config,
    audio_config: Config,
) -> VideoRecognitionOutcome:
    """Settle independent frame and audio recognition for one local MP4."""
    from .errors import Cancelled, OCRLLMError
    from .providers.validate_vision_provider_config import (
        validate_vision_provider_config,
    )
    from .recognize import recognize
    from .recognize_video_frames import recognize_video_frames
    from .validate_config import validate_config
    from .validate_google_mp3_options import validate_google_mp3_options
    from .video.extract_video_audio import (
        _extract_video_audio_from_stable_source,
    )
    from .video.prepare_video_media import prepare_video_media

    validated_image_config = validate_config(image_config)
    _reject_image_persistence(validated_image_config)
    validate_vision_provider_config(validated_image_config)
    validated_audio_config = validate_config(audio_config)
    validate_google_mp3_options(
        (Path("video-audio.mp3"),),
        config=validated_audio_config,
    )

    with prepare_video_media(
        source,
        output_dir=output_dir,
    ) as (snapshot_path, retained_frames):
        output_root = retained_frames[0].path.parent.parent
        audio_artifact: Path | None = None
        audio_result = None
        audio_error: OCRLLMError | None = None
        try:
            audio_artifact = _extract_video_audio_from_stable_source(
                snapshot_path,
                output_path=output_root / "audio.mp3",
            )
        except Cancelled:
            raise
        except OCRLLMError as error:
            audio_error = error

        frame_outcomes = ()
        frame_error: OCRLLMError | None = None
        try:
            frame_outcomes = tuple(
                recognize_video_frames(
                    retained_frames,
                    config=validated_image_config,
                )
            )
        except Cancelled:
            raise
        except OCRLLMError as error:
            frame_error = error

        if audio_artifact is not None:
            try:
                audio_result = recognize(
                    audio_artifact,
                    config=validated_audio_config,
                )
            except Cancelled:
                raise
            except OCRLLMError as error:
                audio_error = error

        assert (audio_result is None) != (audio_error is None)
        return VideoRecognitionOutcome(
            output_root=output_root,
            retained_frames=retained_frames,
            frame_outcomes=frame_outcomes,
            frame_error=frame_error,
            audio_artifact=audio_artifact,
            audio_result=audio_result,
            audio_error=audio_error,
        )


def _reject_image_persistence(config: Config) -> None:
    from .errors import ConfigError

    if config.output_dir is not None or config.resume or config.overwrite:
        raise ConfigError(
            "recognize_video() image recognition is memory-only and does not "
            "accept output_dir, resume, or overwrite.",
            code="CONFIG_INVALID",
        ) from None
