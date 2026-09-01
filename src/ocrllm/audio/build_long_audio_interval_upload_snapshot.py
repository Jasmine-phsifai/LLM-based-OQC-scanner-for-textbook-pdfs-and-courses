"""Describe one materialized interval for provider audio recognition."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..errors import OutputError
from .snapshot_long_mp3 import LongMP3Snapshot


_HASH_CHUNK_BYTES = 1024 * 1024


def build_long_audio_interval_upload_snapshot(
    path: Path,
    *,
    duration_seconds: float,
) -> LongMP3Snapshot:
    """Return actual segment size and digest without decoding it again."""
    digest = hashlib.sha256()
    try:
        byte_size = path.stat().st_size
        with path.open("rb") as stream:
            while chunk := stream.read(_HASH_CHUNK_BYTES):
                digest.update(chunk)
    except (OSError, ValueError) as error:
        raise OutputError(
            "The materialized long-audio interval could not be read.",
            code="OUTPUT_WRITE_FAILED",
        ) from error
    return LongMP3Snapshot(
        path=path,
        byte_size=byte_size,
        sha256=digest.hexdigest(),
        duration_seconds=duration_seconds,
    )
