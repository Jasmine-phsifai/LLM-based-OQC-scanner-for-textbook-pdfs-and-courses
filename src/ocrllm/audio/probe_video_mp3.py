"""Fully decode one video MP3 before choosing one Google audio route."""

from __future__ import annotations

from pathlib import Path

from ..errors import InvalidSource
from .decode_mp3_duration import decode_mp3_duration
from .load_miniaudio import load_miniaudio
from .probe_long_mp3 import MAX_GOOGLE_FILES_AUDIO_DURATION_SECONDS


def probe_video_mp3(snapshot_path: Path) -> float:
    """Return decoded seconds inside the current single-request video range."""
    duration_seconds = decode_mp3_duration(
        snapshot_path,
        backend=load_miniaudio(),
    )
    if duration_seconds > MAX_GOOGLE_FILES_AUDIO_DURATION_SECONDS:
        raise InvalidSource(
            "The video MP3 exceeds the Google single-prompt audio limit.",
            code="SOURCE_TOO_LARGE",
            details={
                "decoded_duration_seconds": duration_seconds,
                "maximum_duration_seconds": (
                    MAX_GOOGLE_FILES_AUDIO_DURATION_SECONDS
                ),
            },
        ) from None
    return duration_seconds
