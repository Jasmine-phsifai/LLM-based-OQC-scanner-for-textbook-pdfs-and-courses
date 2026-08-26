"""Duration and ownership boundaries for the Google Files long-MP3 route."""

from __future__ import annotations

import hashlib
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from ocrllm.errors import InvalidSource


probe_module = importlib.import_module("ocrllm.audio.probe_long_mp3")
snapshot_module = importlib.import_module("ocrllm.audio.snapshot_long_mp3")


class _SizedChunk:
    def __init__(self, sample_count: int) -> None:
        self.sample_count = sample_count

    def __len__(self) -> int:
        return self.sample_count


class _FakeMiniaudio:
    def __init__(self, *, frames: int, sample_rate: int = 10) -> None:
        self.frames = frames
        self.sample_rate = sample_rate

    def mp3_get_file_info(self, _path: str):
        return SimpleNamespace(
            nchannels=1,
            sample_rate=self.sample_rate,
            num_frames=self.frames,
        )

    def mp3_stream_file(self, _path: str, *, frames_to_read: int):
        assert frames_to_read == 4096
        yield _SizedChunk(self.frames)


@pytest.mark.parametrize(
    ("frames", "expected"),
    [(3001, 300.1), (342000, 34200.0)],
)
def test_probe_long_mp3_accepts_single_request_boundaries(
    monkeypatch,
    frames,
    expected,
) -> None:
    monkeypatch.setattr(
        probe_module,
        "load_miniaudio",
        lambda: _FakeMiniaudio(frames=frames),
    )

    assert probe_module.probe_long_mp3(Path("owned.mp3")) == expected


@pytest.mark.parametrize(
    ("frames", "expected_code"),
    [(3000, "SOURCE_INVALID"), (342001, "SOURCE_TOO_LARGE")],
)
def test_probe_long_mp3_rejects_short_or_over_provider_limit(
    monkeypatch,
    frames,
    expected_code,
) -> None:
    monkeypatch.setattr(
        probe_module,
        "load_miniaudio",
        lambda: _FakeMiniaudio(frames=frames),
    )

    with pytest.raises(InvalidSource) as caught:
        probe_module.probe_long_mp3(Path("owned.mp3"))

    assert caught.value.code == expected_code


def test_probe_long_mp3_allows_private_ten_hour_ceiling_only_for_intervals(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        probe_module,
        "load_miniaudio",
        lambda: _FakeMiniaudio(frames=360000),
    )

    assert (
        probe_module.probe_long_mp3(Path("owned.mp3"), interval_mode=True)
        == 36000.0
    )
    with pytest.raises(InvalidSource) as caught:
        probe_module.probe_long_mp3(Path("owned.mp3"))

    assert caught.value.code == "SOURCE_TOO_LARGE"
    assert caught.value.details["maximum_duration_seconds"] == 34200.0


def test_probe_long_mp3_rejects_interval_above_private_ten_hour_ceiling(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        probe_module,
        "load_miniaudio",
        lambda: _FakeMiniaudio(frames=360001),
    )

    with pytest.raises(InvalidSource) as caught:
        probe_module.probe_long_mp3(Path("owned.mp3"), interval_mode=True)

    assert caught.value.code == "SOURCE_TOO_LARGE"
    assert caught.value.details["maximum_duration_seconds"] == 36000.0


def test_snapshot_long_mp3_owns_compact_bytes_and_cleans_up(
    tmp_path,
    monkeypatch,
) -> None:
    source = tmp_path / "lecture.mp3"
    source.write_bytes(b"long-audio-bytes")
    temporary_parent = tmp_path / "snapshots"
    monkeypatch.setattr(
        snapshot_module,
        "probe_long_mp3",
        lambda _path: 301.0,
    )

    with snapshot_module.snapshot_long_mp3(
        source,
        temp_dir=temporary_parent,
    ) as snapshot:
        assert snapshot.path.name == "source.mp3"
        assert snapshot.path.read_bytes() == b"long-audio-bytes"
        assert snapshot.byte_size == len(b"long-audio-bytes")
        assert snapshot.sha256 == hashlib.sha256(b"long-audio-bytes").hexdigest()
        assert snapshot.duration_seconds == 301.0
        owned_root = snapshot.path.parent

    assert not owned_root.exists()
    assert list(temporary_parent.glob("ocrllm-audio-*")) == []


def test_snapshot_long_mp3_rejects_file_limit_before_copy(
    tmp_path,
    monkeypatch,
) -> None:
    source = tmp_path / "lecture.mp3"
    source.write_bytes(b"four")
    monkeypatch.setattr(snapshot_module, "MAX_GOOGLE_FILES_SOURCE_BYTES", 3)

    with pytest.raises(InvalidSource) as caught:
        with snapshot_module.snapshot_long_mp3(
            source,
            temp_dir=tmp_path / "snapshots",
        ):
            raise AssertionError("unreachable")

    assert caught.value.code == "SOURCE_TOO_LARGE"
    assert not (tmp_path / "snapshots").exists()
