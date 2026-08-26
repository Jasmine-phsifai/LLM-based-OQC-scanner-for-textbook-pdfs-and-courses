"""Create one request-owned MP3 for the Google Files long-audio route."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from .probe_long_mp3 import probe_long_mp3
from .snapshot_mp3 import snapshot_mp3


MAX_GOOGLE_FILES_SOURCE_BYTES = 2_000_000_000


@dataclass(frozen=True, slots=True)
class LongMP3Snapshot:
    """Owned long-MP3 path plus Google Files preflight facts."""

    path: Path
    byte_size: int
    sha256: str
    duration_seconds: float


@contextmanager
def snapshot_long_mp3(
    source_path: Path,
    *,
    temp_dir: str | Path | None,
    interval_mode: bool = False,
) -> Iterator[LongMP3Snapshot]:
    """Yield one fully decoded snapshot inside the selected route limits."""
    selected_probe = (
        partial(probe_long_mp3, interval_mode=True)
        if interval_mode
        else probe_long_mp3
    )
    with snapshot_mp3(
        source_path,
        temp_dir=temp_dir,
        maximum_source_bytes=MAX_GOOGLE_FILES_SOURCE_BYTES,
        probe=selected_probe,
    ) as snapshot:
        yield LongMP3Snapshot(
            path=snapshot.path,
            byte_size=snapshot.byte_size,
            sha256=snapshot.sha256,
            duration_seconds=snapshot.duration_seconds,
        )
