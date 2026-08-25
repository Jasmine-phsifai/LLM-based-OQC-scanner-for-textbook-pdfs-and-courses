"""Create one bounded, validated, request-owned short-MP3 snapshot."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .probe_short_mp3 import probe_short_mp3
from .snapshot_mp3 import snapshot_mp3


MAX_SHORT_MP3_SOURCE_BYTES = 25 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ShortMP3Snapshot:
    """Owned short-MP3 path plus validation facts."""

    path: Path
    byte_size: int
    sha256: str
    duration_seconds: float


@contextmanager
def snapshot_short_mp3(
    source_path: Path,
    *,
    temp_dir: str | Path | None,
) -> Iterator[ShortMP3Snapshot]:
    """Yield one fully decoded snapshot inside the A1 limits."""
    with snapshot_mp3(
        source_path,
        temp_dir=temp_dir,
        maximum_source_bytes=MAX_SHORT_MP3_SOURCE_BYTES,
        probe=probe_short_mp3,
    ) as snapshot:
        yield ShortMP3Snapshot(
            path=snapshot.path,
            byte_size=snapshot.byte_size,
            sha256=snapshot.sha256,
            duration_seconds=snapshot.duration_seconds,
        )
