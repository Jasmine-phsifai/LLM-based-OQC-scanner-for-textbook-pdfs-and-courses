"""Fully decode one owned short-MP3 snapshot before provider dispatch."""

from __future__ import annotations

from pathlib import Path

from ..errors import InvalidSource
from .decode_mp3_duration import decode_mp3_duration
from .load_miniaudio import load_miniaudio


MAX_SHORT_MP3_DURATION_SECONDS = 300.0


def probe_short_mp3(snapshot_path: Path) -> float:
    """Return decoded seconds for one immutable MP3 snapshot.

    The caller owns source snapshotting and provider-envelope limits. This
    function owns MP3-specific metadata validation, bounded-memory full decode,
    and the Stage A1 five-minute decoded-duration limit.
    """

    decoded_duration_seconds = decode_mp3_duration(
        snapshot_path,
        backend=load_miniaudio(),
    )
    if decoded_duration_seconds > MAX_SHORT_MP3_DURATION_SECONDS:
        raise InvalidSource(
            "The MP3 source exceeds the five-minute duration limit.",
            code="SOURCE_TOO_LARGE",
            details={
                "decoded_duration_seconds": decoded_duration_seconds,
                "maximum_duration_seconds": MAX_SHORT_MP3_DURATION_SECONDS,
            },
        ) from None
    return decoded_duration_seconds
