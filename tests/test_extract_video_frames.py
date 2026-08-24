"""Public contract for provider-free retained video frames."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import os
from pathlib import Path

import pytest

from ocrllm import OutputError, OutputExists, RetainedVideoFrame, extract_video_frames


def _write_sectioned_mp4(path: Path) -> Path:
    import cv2
    import numpy as np

    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        2.0,
        (64, 48),
    )
    assert writer.isOpened()
    try:
        for value in (20, 230, 70):
            frame = np.full((48, 64, 3), value, dtype=np.uint8)
            for _ in range(10):
                writer.write(frame)
    finally:
        writer.release()
    return path


def _windows_path_units(path: Path) -> int:
    return len(str(path).encode("utf-16-le")) // 2


def _make_directory_with_windows_path_units(base: Path, target_units: int) -> Path:
    current = base
    while _windows_path_units(current) < target_units:
        remaining = target_units - _windows_path_units(current) - 1
        if remaining < 1:
            raise AssertionError("target path length cannot be reached")
        current /= "d" * min(40, remaining)
    assert _windows_path_units(current) == target_units
    current.mkdir(parents=True)
    return current


def test_extract_video_frames_retains_ordered_change_representatives(
    tmp_path: Path,
) -> None:
    import cv2

    source = _write_sectioned_mp4(tmp_path / "lecture.mp4")
    output_parent = tmp_path / "output"

    frames = extract_video_frames(source, output_dir=output_parent)

    assert type(frames) is tuple
    assert [frame.frame_index for frame in frames] == [0, 10, 20]
    assert [frame.timestamp_seconds for frame in frames] == pytest.approx(
        [0.0, 5.0, 10.0]
    )
    assert [frame.path.name for frame in frames] == [
        "frame-00000000.jpg",
        "frame-00000010.jpg",
        "frame-00000020.jpg",
    ]
    assert all(type(frame) is RetainedVideoFrame for frame in frames)
    assert all(frame.path.parent == output_parent / "lecture" / "frames" for frame in frames)
    assert all(frame.path.is_file() for frame in frames)
    assert all(cv2.imread(str(frame.path)).shape[:2] == (48, 64) for frame in frames)

    with pytest.raises(FrozenInstanceError):
        frames[0].frame_index = 1  # type: ignore[misc]


def test_extract_video_frames_rejects_existing_video_directory_without_changes(
    tmp_path: Path,
) -> None:
    source = _write_sectioned_mp4(tmp_path / "lecture.mp4")
    existing_root = tmp_path / "output" / "lecture"
    existing_root.mkdir(parents=True)
    sentinel = existing_root / "keep.txt"
    sentinel.write_text("owned by caller", encoding="utf-8")

    with pytest.raises(OutputExists) as captured:
        extract_video_frames(source, output_dir=tmp_path / "output")

    assert captured.value.code == "OUTPUT_EXISTS"
    assert sentinel.read_text(encoding="utf-8") == "owned by caller"
    assert list(existing_root.iterdir()) == [sentinel]


def test_extract_video_frames_write_failure_publishes_no_partial_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cv2

    source = _write_sectioned_mp4(tmp_path / "lecture.mp4")
    output_parent = tmp_path / "output"
    real_imwrite = cv2.imwrite
    write_count = 0

    def fail_second_write(path, frame):
        nonlocal write_count
        write_count += 1
        if write_count == 2:
            return False
        return real_imwrite(path, frame)

    monkeypatch.setattr(cv2, "imwrite", fail_second_write)

    with pytest.raises(OutputError) as captured:
        extract_video_frames(source, output_dir=output_parent)

    assert captured.value.code == "OUTPUT_WRITE_FAILED"
    assert not (output_parent / "lecture").exists()
    assert not list(output_parent.glob(".ocrllm-video-*"))


def test_extract_video_frames_negative_feedback_adjusts_selection_density() -> None:
    import cv2
    import numpy as np

    from ocrllm.video.select_video_frame_candidates import select_video_frame_candidates
    from ocrllm.video.video_frame_candidate import VideoFrameCandidate

    candidates = []
    for index in range(20):
        thumbnail = np.zeros((128, 128), dtype=np.uint8)
        changed_width = round(128 * index / 20)
        thumbnail[:, :changed_width] = 255
        candidates.append(
            VideoFrameCandidate(
                frame_index=index,
                timestamp_seconds=float(index * 5),
                thumbnail=thumbnail,
            )
        )

    selected = select_video_frame_candidates(
        tuple(candidates),
        duration_seconds=100.0,
        cv2=cv2,
    )

    assert [candidate.frame_index for candidate in selected] == [2, 5, 8, 11, 14, 17, 19]


def test_extract_video_frames_density_cap_keeps_video_ending() -> None:
    import cv2
    import numpy as np

    from ocrllm.video.select_video_frame_candidates import select_video_frame_candidates
    from ocrllm.video.video_frame_candidate import VideoFrameCandidate

    candidates = tuple(
        VideoFrameCandidate(
            frame_index=index,
            timestamp_seconds=float(index * 36),
            thumbnail=np.full(
                (128, 128),
                255 if index % 2 else 0,
                dtype=np.uint8,
            ),
        )
        for index in range(100)
    )

    selected = select_video_frame_candidates(
        candidates,
        duration_seconds=3600.0,
        cv2=cv2,
    )

    selected_indices = tuple(candidate.frame_index for candidate in selected)
    assert len(selected_indices) == 40
    assert selected_indices[0] == 0
    assert selected_indices[-1] == 99
    assert all(
        selected_indices[index] < selected_indices[index + 1]
        for index in range(len(selected_indices) - 1)
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows legacy path-limit regression")
def test_extract_video_frames_does_not_amplify_near_limit_paths(
    tmp_path: Path,
) -> None:
    if _windows_path_units(tmp_path) >= 130:
        pytest.skip("pytest temporary root is already beyond the controlled path range")
    long_stem = "v" * 96
    source = _write_sectioned_mp4(tmp_path / f"{long_stem}.mp4")
    output_parent = _make_directory_with_windows_path_units(tmp_path / "out", 130)

    frames = extract_video_frames(source, output_dir=output_parent)

    created_paths = (
        output_parent / long_stem,
        output_parent / long_stem / "frames",
        *(frame.path for frame in frames),
    )
    assert max(_windows_path_units(path) for path in created_paths) <= 259
    assert all(path.exists() for path in created_paths)
