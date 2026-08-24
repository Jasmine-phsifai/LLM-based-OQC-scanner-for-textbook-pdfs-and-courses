"""Read immutable frame identity from one settled video frame group."""

from __future__ import annotations

import math
from collections.abc import Mapping

from .batch_item_outcome import BatchItemOutcome


def read_video_frame_group_identity(
    item: BatchItemOutcome,
) -> tuple[tuple[int, ...], tuple[float, ...]]:
    """Return validated frame indices and timestamps for one group outcome."""
    source: Mapping[str, object]
    if item.result is not None:
        source = item.result.metadata
    else:
        assert item.error is not None
        source = item.error.details
    indices = source.get("video_frame_indices")
    timestamps = source.get("video_frame_timestamps_seconds")
    if (
        type(indices) is not tuple
        or not indices
        or any(type(index) is not int or index < 0 for index in indices)
        or type(timestamps) is not tuple
        or len(timestamps) != len(indices)
        or any(
            not isinstance(timestamp, (int, float))
            or isinstance(timestamp, bool)
            or not math.isfinite(float(timestamp))
            or float(timestamp) < 0
            for timestamp in timestamps
        )
    ):
        raise ValueError("video frame group identity is missing or invalid") from None
    return indices, tuple(float(timestamp) for timestamp in timestamps)
