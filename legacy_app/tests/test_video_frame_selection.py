"""Regression coverage for legacy temporal video-frame selection."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from OCRLLM.processors.video import VideoProcessor


class _RecordingCapture:
    def __init__(self) -> None:
        self.frame_indices: list[int] = []
        self.released = False

    def isOpened(self) -> bool:
        return True

    def set(self, _property: int, frame_index: int) -> bool:
        self.frame_indices.append(frame_index)
        return True

    def read(self) -> tuple[bool, object]:
        return True, object()

    def release(self) -> None:
        self.released = True


def _make_processor() -> VideoProcessor:
    processor = VideoProcessor.__new__(VideoProcessor)
    processor.cfg = SimpleNamespace(
        video=SimpleNamespace(
            frame_interval=5.0,
            change_threshold=0.15,
            drift_threshold=0.10,
            max_segment_sec=150.0,
            phash_threshold=3,
        )
    )
    processor.tracker = SimpleNamespace(update_phase=lambda *_args, **_kwargs: None)
    processor._check_cancelled = lambda: None
    return processor


@pytest.mark.parametrize(
    ("total_frames", "expected_indices"),
    (
        (150, [0, 50, 100, 149]),
        (151, [0, 50, 100, 150]),
    ),
)
def test_coarse_scan_always_samples_exact_final_frame(
    tmp_path: Path,
    total_frames: int,
    expected_indices: list[int],
) -> None:
    processor = _make_processor()
    capture = _RecordingCapture()
    processor._open_video_capture = lambda _path: capture

    def retain_candidate(
        _frame,
        frame_index,
        fps,
        candidates,
        _skipped,
        _temp_dir,
    ) -> None:
        candidates.append(
            {
                "frame_idx": frame_index,
                "timestamp": frame_index / fps,
            }
        )

    processor._extract_candidate_from_frame = retain_candidate

    candidates = processor._coarse_scan(
        "lecture.mp4",
        fps=10.0,
        total_frames=total_frames,
        cand_temp_dir=str(tmp_path),
        num_workers=1,
    )

    assert capture.frame_indices == expected_indices
    assert [candidate["frame_idx"] for candidate in candidates] == expected_indices
    assert capture.released


def test_coarse_scan_reads_exact_final_frame_from_real_mp4(tmp_path: Path) -> None:
    import cv2
    import numpy as np

    source = tmp_path / "ending-change.mp4"
    writer = cv2.VideoWriter(
        str(source),
        cv2.VideoWriter_fourcc(*"mp4v"),
        2.0,
        (64, 48),
    )
    assert writer.isOpened()
    try:
        for value in (20, 20, 20, 20, 20, 230):
            writer.write(np.full((48, 64, 3), value, dtype=np.uint8))
    finally:
        writer.release()

    processor = _make_processor()
    processor.cfg.video.min_content_ratio = 0.0
    candidates = processor._coarse_scan(
        str(source),
        fps=2.0,
        total_frames=6,
        cand_temp_dir=str(tmp_path),
        num_workers=1,
    )

    assert [candidate["frame_idx"] for candidate in candidates] == [0, 5]
    assert all(Path(candidate["temp_path"]).is_file() for candidate in candidates)


def test_density_cap_preserves_first_and_final_selected_candidates() -> None:
    processor = _make_processor()
    candidates = [
        {"frame_idx": index, "timestamp": float(index)}
        for index in range(11)
    ]
    processor._segment_and_select = lambda *_args, **_kwargs: list(candidates)

    selected = processor._auto_calibrate_segmentation(candidates, duration=1.0)

    assert len(selected) == 10
    assert selected[0]["frame_idx"] == 0
    assert selected[-1]["frame_idx"] == 10
    assert all(
        selected[index]["frame_idx"] < selected[index + 1]["frame_idx"]
        for index in range(len(selected) - 1)
    )
