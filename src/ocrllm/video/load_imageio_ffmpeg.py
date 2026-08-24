"""Load the optional FFmpeg executable for video audio extraction."""

from __future__ import annotations

import stat
from pathlib import Path

from ..errors import DependencyMissing, VideoError


def load_imageio_ffmpeg_executable() -> Path:
    """Return one regular FFmpeg executable from the video extra."""
    try:
        import imageio_ffmpeg
    except (ImportError, OSError) as error:
        raise DependencyMissing(
            "Video audio extraction requires the optional 'video' extra.",
            details={"extra": "video"},
        ) from error

    try:
        executable = Path(imageio_ffmpeg.get_ffmpeg_exe())
        executable_stat = executable.stat()
    except Exception as error:
        raise VideoError(
            "The video audio backend is unavailable.",
            code="VIDEO_BACKEND_UNAVAILABLE",
            details={"extra": "video"},
        ) from error
    if not stat.S_ISREG(executable_stat.st_mode):
        raise VideoError(
            "The video audio backend is unavailable.",
            code="VIDEO_BACKEND_UNAVAILABLE",
            details={"extra": "video"},
        ) from None
    return executable
