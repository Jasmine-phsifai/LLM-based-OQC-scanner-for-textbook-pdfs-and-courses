"""Group retained video frames for one bounded vision request."""

from __future__ import annotations

from .retained_video_frame import RetainedVideoFrame


VIDEO_FRAME_GROUP_LIMIT = 8


def group_retained_video_frames(
    frames: tuple[RetainedVideoFrame, ...],
    group_size: int,
) -> tuple[tuple[RetainedVideoFrame, ...], ...]:
    """Return ordered nonempty groups without changing frame identity."""
    if type(frames) is not tuple or not frames:
        raise ValueError("retained video frames must be a nonempty exact tuple")
    if type(group_size) is not int or not 1 <= group_size <= VIDEO_FRAME_GROUP_LIMIT:
        raise ValueError("video frame group size is invalid") from None
    return tuple(
        frames[start : start + group_size]
        for start in range(0, len(frames), group_size)
    )
