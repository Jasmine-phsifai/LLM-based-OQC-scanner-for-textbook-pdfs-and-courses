"""Create one product-bounded MP3 snapshot for explicit audio slices."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .probe_product_mp3 import (
    MAX_PRODUCT_MP3_SOURCE_BYTES,
    probe_product_mp3,
)
from .snapshot_long_mp3 import LongMP3Snapshot
from .snapshot_mp3 import snapshot_mp3


@contextmanager
def snapshot_product_mp3(
    source_path: Path,
    *,
    temp_dir: str | Path | None = None,
) -> Iterator[LongMP3Snapshot]:
    """Yield one fully decoded snapshot through the ten-hour product limit."""
    with snapshot_mp3(
        source_path,
        temp_dir=temp_dir,
        maximum_source_bytes=MAX_PRODUCT_MP3_SOURCE_BYTES,
        probe=probe_product_mp3,
    ) as snapshot:
        yield LongMP3Snapshot(
            path=snapshot.path,
            byte_size=snapshot.byte_size,
            sha256=snapshot.sha256,
            duration_seconds=snapshot.duration_seconds,
        )
