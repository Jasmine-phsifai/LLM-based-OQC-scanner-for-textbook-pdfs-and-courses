"""Recognize one ordered tuple of library-retained video frames."""

from __future__ import annotations

from .batch_item_outcome import BatchItemOutcome
from .config import Config
from .errors import ConfigError, InvalidSource
from .recognize_batch import recognize_batch
from .resolve_effective_image_limit import resolve_effective_image_limit
from .retained_video_frame import RetainedVideoFrame
from .validate_config import validate_config


_VIDEO_FRAME_GROUP_LIMIT = 8


def recognize_video_frames(
    frames: tuple[RetainedVideoFrame, ...],
    *,
    config: Config | None = None,
) -> list[BatchItemOutcome]:
    """Recognize ordered retained JPEGs in groups of at most eight.

    This boundary is memory-only until the video composition and recovery
    contract is defined. Each outcome corresponds to one image group, not one
    individual frame.
    """
    cfg = validate_config(config)
    _reject_video_persistence(cfg)
    _validate_retained_frame_tuple(frames)
    configured_limit, _ = resolve_effective_image_limit(cfg)
    group_size = min(_VIDEO_FRAME_GROUP_LIMIT, configured_limit)
    groups = tuple(
        tuple(frame.path for frame in frames[start : start + group_size])
        for start in range(0, len(frames), group_size)
    )
    return recognize_batch(groups, config=cfg)


def _reject_video_persistence(config: Config) -> None:
    if config.output_dir is not None or config.resume or config.overwrite:
        raise ConfigError(
            "recognize_video_frames() is memory-only and does not accept "
            "output_dir, resume, or overwrite.",
            code="CONFIG_INVALID",
        ) from None


def _validate_retained_frame_tuple(frames: object) -> None:
    if type(frames) is not tuple or not frames:
        raise InvalidSource(
            "recognize_video_frames() requires a nonempty exact tuple.",
            code="SOURCE_INVALID",
        ) from None

    previous: RetainedVideoFrame | None = None
    for frame in frames:
        if type(frame) is not RetainedVideoFrame:
            raise InvalidSource(
                "Every video frame must be an exact RetainedVideoFrame instance.",
                code="SOURCE_INVALID",
            ) from None
        if previous is not None and (
            frame.frame_index <= previous.frame_index
            or frame.timestamp_seconds < previous.timestamp_seconds
        ):
            raise InvalidSource(
                "Retained video frames must remain in source order.",
                code="SOURCE_INVALID",
            ) from None
        previous = frame
