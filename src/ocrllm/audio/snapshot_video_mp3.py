"""Create one request-owned MP3 before video audio-route selection."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial
from pathlib import Path

from .probe_video_mp3 import probe_video_mp3
from .snapshot_long_mp3 import MAX_GOOGLE_FILES_SOURCE_BYTES
from .snapshot_mp3 import MP3Snapshot, snapshot_mp3


@contextmanager
def snapshot_video_mp3(
    source_path: Path,
    *,
    temp_dir: str | Path | None,
    interval_mode: bool = False,
) -> Iterator[MP3Snapshot]:
    """Yield one decoded snapshot suitable for exactly one audio route."""
    selected_probe = (
        partial(probe_video_mp3, interval_mode=True)
        if interval_mode
        else probe_video_mp3
    )
    with snapshot_mp3(
        source_path,
        temp_dir=temp_dir,
        maximum_source_bytes=MAX_GOOGLE_FILES_SOURCE_BYTES,
        probe=selected_probe,
    ) as snapshot:
        yield snapshot
