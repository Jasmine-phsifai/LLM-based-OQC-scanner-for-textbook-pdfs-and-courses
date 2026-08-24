"""Public contract for the first provider-free video slice."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ocrllm import DependencyMissing, VideoError, VideoInfo, inspect_video


def _write_short_mp4(path: Path) -> Path:
    import cv2
    import numpy as np

    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        10.0,
        (64, 48),
    )
    assert writer.isOpened()
    try:
        for index in range(8):
            frame = np.full((48, 64, 3), index * 20, dtype=np.uint8)
            writer.write(frame)
    finally:
        writer.release()
    return path


def test_public_inspect_video_reads_one_real_mp4(tmp_path: Path) -> None:
    source = _write_short_mp4(tmp_path / "lecture.mp4")

    info = inspect_video(source)

    assert type(info) is VideoInfo
    assert info.frame_count == 8
    assert info.frames_per_second == pytest.approx(10.0)
    assert info.duration_seconds == pytest.approx(0.8)
    assert info.width_pixels == 64
    assert info.height_pixels == 48


def test_public_inspect_video_rejects_corrupt_mp4(tmp_path: Path) -> None:
    source = tmp_path / "broken.mp4"
    source.write_bytes(b"not a video")

    with pytest.raises(VideoError) as captured:
        inspect_video(source)

    assert captured.value.code == "VIDEO_INVALID"


def test_inspect_video_releases_capture_when_metadata_is_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "invalid-metadata.mp4"
    source.write_bytes(b"placeholder")

    class FakeCapture:
        released = False

        def isOpened(self):
            return True

        def get(self, property_id):
            return 0.0

        def read(self):
            raise AssertionError("invalid metadata must fail before frame decode")

        def release(self):
            self.released = True

    capture = FakeCapture()

    class FakeOpenCV:
        CAP_PROP_FPS = 1
        CAP_PROP_FRAME_COUNT = 2
        CAP_PROP_FRAME_WIDTH = 3
        CAP_PROP_FRAME_HEIGHT = 4

        @staticmethod
        def VideoCapture(path):
            assert path == str(source)
            return capture

    monkeypatch.setattr(
        "ocrllm.video.inspect_video.load_opencv",
        lambda: FakeOpenCV,
    )

    with pytest.raises(VideoError) as captured:
        inspect_video(source)

    assert captured.value.code == "VIDEO_INVALID"
    assert capture.released is True


def test_inspect_video_maps_backend_decode_failure_and_releases_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "decode-failure.mp4"
    source.write_bytes(b"placeholder")

    class FakeCapture:
        released = False

        def isOpened(self):
            return True

        def get(self, property_id):
            return {1: 10.0, 2: 8.0, 3: 64.0, 4: 48.0}[property_id]

        def read(self):
            raise RuntimeError("private backend detail")

        def release(self):
            self.released = True

    capture = FakeCapture()

    class FakeOpenCV:
        CAP_PROP_FPS = 1
        CAP_PROP_FRAME_COUNT = 2
        CAP_PROP_FRAME_WIDTH = 3
        CAP_PROP_FRAME_HEIGHT = 4

        @staticmethod
        def VideoCapture(path):
            return capture

    monkeypatch.setattr(
        "ocrllm.video.inspect_video.load_opencv",
        lambda: FakeOpenCV,
    )

    with pytest.raises(VideoError) as captured:
        inspect_video(source)

    assert str(captured.value) == "The video backend could not inspect the source."
    assert "private backend detail" not in str(captured.value)
    assert capture.released is True


def test_load_opencv_maps_missing_video_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    from ocrllm.video.load_opencv import load_opencv

    monkeypatch.setitem(sys.modules, "cv2", None)

    with pytest.raises(DependencyMissing) as captured:
        load_opencv()

    assert captured.value.code == "DEPENDENCY_MISSING"
    assert captured.value.details["extra"] == "video"


def test_inspect_video_maps_open_check_failure_and_releases_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "open-check-failure.mp4"
    source.write_bytes(b"placeholder")

    class FakeCapture:
        released = False

        def isOpened(self):
            raise RuntimeError("private backend detail")

        def release(self):
            self.released = True

    capture = FakeCapture()

    class FakeOpenCV:
        CAP_PROP_FPS = 1
        CAP_PROP_FRAME_COUNT = 2
        CAP_PROP_FRAME_WIDTH = 3
        CAP_PROP_FRAME_HEIGHT = 4

        @staticmethod
        def VideoCapture(path):
            return capture

    monkeypatch.setattr(
        "ocrllm.video.inspect_video.load_opencv",
        lambda: FakeOpenCV,
    )

    with pytest.raises(VideoError) as captured:
        inspect_video(source)

    assert str(captured.value) == "The video backend could not open the source."
    assert "private backend detail" not in str(captured.value)
    assert capture.released is True
