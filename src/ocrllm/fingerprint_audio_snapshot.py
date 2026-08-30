"""Build resume identity from one validated owned audio snapshot."""

from __future__ import annotations

from pathlib import Path

from .audio.snapshot_long_mp3 import LongMP3Snapshot
from .contracts.source_fingerprint import SourceFingerprint
from .errors import InvalidSource, OutputError


def fingerprint_audio_snapshot(
    source_path: Path,
    snapshot: LongMP3Snapshot,
) -> SourceFingerprint:
    """Return the original file URI with exact owned bytes and digest."""
    try:
        source_uri = source_path.resolve(strict=True).as_uri()
    except FileNotFoundError:
        raise InvalidSource(
            "The audio source disappeared before resume identity was built.",
            code="SOURCE_NOT_FOUND",
        ) from None
    except (OSError, ValueError):
        raise OutputError(
            "Validated audio bytes could not be fingerprinted for resume.",
            code="OUTPUT_WRITE_FAILED",
        ) from None
    return SourceFingerprint(
        uri=source_uri,
        byte_size=snapshot.byte_size,
        sha256=snapshot.sha256,
    )
