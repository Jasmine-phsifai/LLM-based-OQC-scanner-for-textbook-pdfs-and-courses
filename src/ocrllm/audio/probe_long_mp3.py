"""Fully decode one MP3 for the single-request Google Files route."""

from __future__ import annotations

from pathlib import Path

from ..errors import InvalidSource
from .decode_mp3_duration import decode_mp3_duration
from .load_miniaudio import load_miniaudio
from .probe_short_mp3 import MAX_SHORT_MP3_DURATION_SECONDS


MAX_GOOGLE_FILES_AUDIO_DURATION_SECONDS = 9.5 * 60 * 60
MAX_PRODUCT_AUDIO_DURATION_SECONDS = 10 * 60 * 60


def probe_long_mp3(snapshot_path: Path, *, interval_mode: bool = False) -> float:
    """Return decoded seconds inside the selected whole or interval route."""
    duration_seconds = decode_mp3_duration(
        snapshot_path,
        backend=load_miniaudio(),
    )
    if duration_seconds <= MAX_SHORT_MP3_DURATION_SECONDS:
        raise InvalidSource(
            "The MP3 source belongs to the short-audio route.",
            code="SOURCE_INVALID",
            details={
                "decoded_duration_seconds": duration_seconds,
                "minimum_exclusive_duration_seconds": (
                    MAX_SHORT_MP3_DURATION_SECONDS
                ),
            },
        ) from None
    maximum_duration_seconds = (
        MAX_PRODUCT_AUDIO_DURATION_SECONDS
        if interval_mode
        else MAX_GOOGLE_FILES_AUDIO_DURATION_SECONDS
    )
    if duration_seconds > maximum_duration_seconds:
        raise InvalidSource(
            "The MP3 source exceeds the selected audio-route limit.",
            code="SOURCE_TOO_LARGE",
            details={
                "decoded_duration_seconds": duration_seconds,
                "maximum_duration_seconds": maximum_duration_seconds,
            },
        ) from None
    return duration_seconds
