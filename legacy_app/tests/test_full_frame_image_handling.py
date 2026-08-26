"""Regression coverage for the no-board-cropping product rule."""

from __future__ import annotations

from types import SimpleNamespace

import cv2
import numpy as np
from PIL import Image

from OCRLLM.config import AppConfig
from OCRLLM.imaging.prepare_board_image import prepare_board_image
from OCRLLM.processors.video import VideoProcessor


def test_prepare_board_image_preserves_complete_source_frame(tmp_path) -> None:
    source = tmp_path / "multiple-boards.png"
    image = Image.new("RGB", (12, 8), "black")
    image.putpixel((0, 0), (255, 0, 0))
    image.putpixel((11, 0), (0, 255, 0))
    image.putpixel((0, 7), (0, 0, 255))
    image.putpixel((11, 7), (255, 255, 0))
    image.save(source)
    output = tmp_path / "prepared.png"

    prepare_board_image(
        str(source),
        str(output),
        max_side=2048,
        quality=90,
    )

    assert output.read_bytes() == source.read_bytes()
    with Image.open(output) as prepared:
        assert prepared.size == (12, 8)
        assert prepared.getpixel((0, 0)) == (255, 0, 0)
        assert prepared.getpixel((11, 0)) == (0, 255, 0)
        assert prepared.getpixel((0, 7)) == (0, 0, 255)
        assert prepared.getpixel((11, 7)) == (255, 255, 0)


def test_prepare_board_image_downscales_without_cropping_edges(tmp_path) -> None:
    source = tmp_path / "board-and-projection.png"
    image = Image.new("RGB", (120, 80), "black")
    image.paste((255, 0, 0), (0, 0, 12, 80))
    image.paste((0, 255, 0), (108, 0, 120, 80))
    image.save(source)
    output = tmp_path / "prepared.png"

    prepare_board_image(
        str(source),
        str(output),
        max_side=60,
        quality=90,
    )

    with Image.open(output) as prepared:
        assert prepared.size == (60, 40)
        assert prepared.getpixel((0, 20))[0] > 200
        assert prepared.getpixel((59, 20))[1] > 200


def test_deleted_crop_configuration_is_not_exposed() -> None:
    assert not hasattr(AppConfig(), "imaging")


def test_video_candidate_publishes_the_complete_frame(tmp_path) -> None:
    processor = VideoProcessor.__new__(VideoProcessor)
    processor.cfg = SimpleNamespace(
        video=SimpleNamespace(min_content_ratio=0.0),
    )
    frame = np.zeros((20, 30, 3), dtype=np.uint8)
    frame[:, :5] = (0, 0, 255)
    frame[:, -5:] = (0, 255, 0)
    candidates: list[dict] = []
    skipped = {"blank": 0}

    processor._extract_candidate_from_frame(
        frame,
        12,
        2.0,
        candidates,
        skipped,
        str(tmp_path),
    )

    assert skipped == {"blank": 0}
    assert len(candidates) == 1
    saved = cv2.imdecode(
        np.fromfile(candidates[0]["temp_path"], dtype=np.uint8),
        cv2.IMREAD_COLOR,
    )
    assert saved.shape[:2] == (20, 30)
    assert saved[:, :5, 2].mean() > 200
    assert saved[:, -5:, 1].mean() > 200
