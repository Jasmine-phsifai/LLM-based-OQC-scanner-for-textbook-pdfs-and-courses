"""Actual filesystem facts for one materialized interval upload."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ocrllm.audio.build_long_audio_interval_upload_snapshot import (
    build_long_audio_interval_upload_snapshot,
)
from ocrllm.errors import OutputError


def test_interval_upload_snapshot_uses_actual_segment_bytes(tmp_path: Path) -> None:
    segment = tmp_path / "segment.mp3"
    payload = b"materialized interval bytes"
    segment.write_bytes(payload)

    snapshot = build_long_audio_interval_upload_snapshot(
        segment,
        duration_seconds=330.0,
    )

    assert snapshot.path == segment
    assert snapshot.byte_size == len(payload)
    assert snapshot.sha256 == hashlib.sha256(payload).hexdigest()
    assert snapshot.duration_seconds == 330.0


def test_interval_upload_snapshot_rejects_missing_segment(tmp_path: Path) -> None:
    with pytest.raises(OutputError) as captured:
        build_long_audio_interval_upload_snapshot(
            tmp_path / "missing.mp3",
            duration_seconds=330.0,
        )

    assert captured.value.code == "OUTPUT_WRITE_FAILED"
