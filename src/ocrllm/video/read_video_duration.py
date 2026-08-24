"""Read one video's container duration through the bundled FFmpeg wrapper."""

from __future__ import annotations

import math
from pathlib import Path

from ..errors import DependencyMissing, VideoError


def read_video_duration(source: Path) -> float:
    """Return one positive finite container duration without decoding frames."""
    try:
        import imageio_ffmpeg
    except (ImportError, OSError) as error:
        raise DependencyMissing(
            "Video inspection requires the optional 'video' extra.",
            details={"extra": "video"},
        ) from error

    try:
        reader = imageio_ffmpeg.read_frames(source)
        try:
            metadata = next(reader)
            duration = metadata.get("duration")
        finally:
            reader.close()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        raise VideoError(
            "The video backend could not read the container duration.",
            code="VIDEO_INVALID",
        ) from error
    if (
        not isinstance(duration, (int, float))
        or isinstance(duration, bool)
        or not math.isfinite(float(duration))
        or float(duration) <= 0
    ):
        raise VideoError(
            "The video container duration is invalid.",
            code="VIDEO_INVALID",
        ) from None
    return float(duration)
