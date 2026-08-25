"""Recognize one ordered tuple of library-retained video frames."""

from __future__ import annotations

from .batch_item_outcome import BatchItemOutcome
from .config import Config
from .retained_video_frame import RetainedVideoFrame


_VIDEO_FRAME_GROUP_LIMIT = 8


def recognize_video_frames(
    frames: tuple[RetainedVideoFrame, ...],
    *,
    config: Config | None = None,
) -> list[BatchItemOutcome]:
    """Recognize ordered retained JPEGs in groups of at most eight.

    This boundary is memory-only. Composition and publication are separate
    public steps; video recovery remains unavailable. Each outcome corresponds
    to one image group, not one individual frame.
    """
    from .providers.validate_vision_provider_config import (
        validate_vision_provider_config,
    )
    from .recognize_batch import recognize_batch
    from .resolve_effective_image_limit import resolve_effective_image_limit
    from .validate_config import validate_config

    cfg = validate_config(config)
    _reject_video_persistence(cfg)
    validate_vision_provider_config(cfg)
    _validate_retained_frame_tuple(frames)
    configured_limit, _ = resolve_effective_image_limit(cfg)
    group_size = min(_VIDEO_FRAME_GROUP_LIMIT, configured_limit)
    frame_groups = _group_retained_frames(frames, group_size)
    groups = tuple(
        tuple(frame.path for frame in frame_group)
        for frame_group in frame_groups
    )
    outcomes = recognize_batch(groups, config=cfg)
    return [
        _attach_video_frame_group_identity(outcome, group)
        for outcome, group in zip(outcomes, frame_groups)
    ]


def _group_retained_frames(
    frames: tuple[RetainedVideoFrame, ...],
    group_size: int,
) -> tuple[tuple[RetainedVideoFrame, ...], ...]:
    return tuple(
        frames[start : start + group_size]
        for start in range(0, len(frames), group_size)
    )


def _attach_video_frame_group_identity(
    outcome: BatchItemOutcome,
    frames: tuple[RetainedVideoFrame, ...],
) -> BatchItemOutcome:
    from dataclasses import replace

    frame_indices = tuple(frame.frame_index for frame in frames)
    frame_timestamps = tuple(frame.timestamp_seconds for frame in frames)
    if outcome.result is not None:
        metadata = dict(outcome.result.metadata)
        metadata["video_frame_indices"] = frame_indices
        metadata["video_frame_timestamps_seconds"] = frame_timestamps
        return BatchItemOutcome(
            index=outcome.index,
            result=replace(outcome.result, metadata=metadata),
        )

    assert outcome.error is not None
    outcome.error._add_safe_detail("video_frame_indices", frame_indices)
    outcome.error._add_safe_detail(
        "video_frame_timestamps_seconds",
        frame_timestamps,
    )
    return outcome


def _reject_video_persistence(config: Config) -> None:
    from .errors import ConfigError

    if config.output_dir is not None or config.resume or config.overwrite:
        raise ConfigError(
            "recognize_video_frames() is memory-only and does not accept "
            "output_dir, resume, or overwrite.",
            code="CONFIG_INVALID",
        ) from None


def _validate_retained_frame_tuple(frames: object) -> None:
    from .errors import InvalidSource

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
