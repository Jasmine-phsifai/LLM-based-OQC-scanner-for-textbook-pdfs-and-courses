"""Attach retained-frame identity to one image-group outcome."""

from __future__ import annotations

from dataclasses import replace

from .batch_item_outcome import BatchItemOutcome
from .retained_video_frame import RetainedVideoFrame


def attach_video_frame_group_identity(
    outcome: BatchItemOutcome,
    frames: tuple[RetainedVideoFrame, ...],
) -> BatchItemOutcome:
    """Return an outcome that names the exact retained frames it covers."""
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
