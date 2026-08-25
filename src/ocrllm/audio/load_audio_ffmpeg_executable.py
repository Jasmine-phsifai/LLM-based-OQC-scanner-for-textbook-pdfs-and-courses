"""Load the optional FFmpeg executable for audio interval materialization."""

from __future__ import annotations

import stat
from pathlib import Path

from ..errors import DependencyMissing


def load_audio_ffmpeg_executable() -> Path:
    """Return the regular FFmpeg executable installed by the audio extra."""
    try:
        import imageio_ffmpeg
    except (ImportError, OSError) as error:
        raise DependencyMissing(
            "Long-audio intervals require the optional 'audio' extra.",
            details={"extra": "audio"},
        ) from error

    try:
        executable = Path(imageio_ffmpeg.get_ffmpeg_exe())
        executable_stat = executable.stat()
    except Exception as error:
        raise DependencyMissing(
            "The long-audio interval backend is unavailable.",
            details={"extra": "audio"},
        ) from error
    if not stat.S_ISREG(executable_stat.st_mode):
        raise DependencyMissing(
            "The long-audio interval backend is unavailable.",
            details={"extra": "audio"},
        ) from None
    return executable
