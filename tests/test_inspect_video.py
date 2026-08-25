"""Public contract for the first provider-free video slice."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ocrllm import (
    DependencyMissing,
    InvalidSource,
    VideoError,
    VideoInfo,
    inspect_video,
)


def _write_short_mp4(
    path: Path,
    *,
    frame_count: int = 8,
    frames_per_second: float = 10.0,
    width_pixels: int = 64,
    height_pixels: int = 48,
) -> Path:
    import cv2
    import numpy as np

    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        frames_per_second,
        (width_pixels, height_pixels),
    )
    assert writer.isOpened()
    try:
        for index in range(frame_count):
            frame = np.full(
                (height_pixels, width_pixels, 3),
                index % 255,
                dtype=np.uint8,
            )
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


def test_inspect_video_rejects_source_replaced_before_duration_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_short_mp4(tmp_path / "source.mp4")
    replacement = _write_short_mp4(
        tmp_path / "replacement.mp4",
        frame_count=30,
        frames_per_second=5.0,
        width_pixels=96,
        height_pixels=72,
    )
    module = __import__("ocrllm.video.inspect_video", fromlist=["unused"])
    real_read_duration = module.read_video_duration
    replacement_bytes = replacement.read_bytes()

    def replace_then_read_duration(source_path: Path) -> float:
        source.write_bytes(replacement_bytes)
        return real_read_duration(source_path)

    monkeypatch.setattr(
        module,
        "read_video_duration",
        replace_then_read_duration,
    )

    with pytest.raises(InvalidSource) as captured:
        inspect_video(source)

    assert captured.value.code == "SOURCE_INVALID"
    assert source.is_file()


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


def test_inspect_video_maps_missing_ffmpeg_metadata_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_short_mp4(tmp_path / "lecture.mp4")
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)

    with pytest.raises(DependencyMissing) as captured:
        inspect_video(source)

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
