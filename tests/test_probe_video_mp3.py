"""Duration routing boundaries for one video-owned MP3 snapshot."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from ocrllm.errors import InvalidSource


probe_module = importlib.import_module("ocrllm.audio.probe_video_mp3")


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
    [(3000, 300.0), (3001, 300.1), (342000, 34200.0)],
)
def test_probe_video_mp3_accepts_both_single_request_routes(
    monkeypatch: pytest.MonkeyPatch,
    frames: int,
    expected: float,
) -> None:
    monkeypatch.setattr(
        probe_module,
        "load_miniaudio",
        lambda: _FakeMiniaudio(frames=frames),
    )

    assert probe_module.probe_video_mp3(Path("owned.mp3")) == expected


def test_probe_video_mp3_rejects_above_single_request_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        probe_module,
        "load_miniaudio",
        lambda: _FakeMiniaudio(frames=342001),
    )

    with pytest.raises(InvalidSource) as caught:
        probe_module.probe_video_mp3(Path("owned.mp3"))

    assert caught.value.code == "SOURCE_TOO_LARGE"
    assert caught.value.details["maximum_duration_seconds"] == 34200.0
