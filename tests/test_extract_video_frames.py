"""Public contract for provider-free retained video frames."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import os
from pathlib import Path
import subprocess

import pytest

from ocrllm import (
    OutputError,
    OutputExists,
    RetainedVideoFrame,
    VideoError,
    VideoInfo,
    extract_video_frames,
    inspect_video,
)


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


def _write_final_frame_change_mp4(path: Path) -> Path:
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
        for value in (20, 20, 20, 20, 20, 230):
            writer.write(np.full((48, 64, 3), value, dtype=np.uint8))
    finally:
        writer.release()
    return path


def _write_equal_luma_color_change_mp4(path: Path) -> Path:
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
        for color in ((0, 0, 200), (0, 102, 0), (0, 0, 200)):
            frame = np.full((48, 64, 3), color, dtype=np.uint8)
            for _ in range(10):
                writer.write(frame)
    finally:
        writer.release()
    return path


def _write_variable_frame_rate_mp4(path: Path) -> Path:
    import cv2
    import imageio_ffmpeg
    import numpy as np

    frame_paths = tuple(path.with_name(f"vfr-{index}.png") for index in range(4))
    for frame_path, value in zip(frame_paths, (20, 90, 160, 230)):
        assert cv2.imwrite(
            str(frame_path),
            np.full((48, 64, 3), value, dtype=np.uint8),
        )
    concat_path = path.with_suffix(".txt")
    concat_path.write_text(
        "\n".join(
            (
                f"file '{frame_paths[0].as_posix()}'",
                "duration 1.0",
                f"file '{frame_paths[1].as_posix()}'",
                "duration 2.0",
                f"file '{frame_paths[2].as_posix()}'",
                "duration 0.5",
                f"file '{frame_paths[3].as_posix()}'",
                "duration 1.0",
                f"file '{frame_paths[3].as_posix()}'",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        (
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-fps_mode",
            "vfr",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert completed.returncode == 0
    return path


def _write_rotated_display_mp4(path: Path) -> Path:
    import cv2
    import imageio_ffmpeg
    import numpy as np

    encoded_path = path.with_name(f"encoded-{path.name}")
    writer = cv2.VideoWriter(
        str(encoded_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        2.0,
        (96, 64),
    )
    assert writer.isOpened()
    try:
        frame = np.zeros((64, 96, 3), dtype=np.uint8)
        frame[:32, :48] = (0, 0, 255)
        frame[32:, 48:] = (255, 0, 0)
        writer.write(frame)
        writer.write(frame)
    finally:
        writer.release()

    completed = subprocess.run(
        (
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-display_rotation",
            "90",
            "-i",
            str(encoded_path),
            "-c",
            "copy",
            str(path),
        ),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert completed.returncode == 0
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
    assert [frame.frame_index for frame in frames] == [0, 10, 29]
    assert [frame.timestamp_seconds for frame in frames] == pytest.approx(
        [0.0, 5.0, 14.5]
    )
    assert [frame.path.name for frame in frames] == [
        "frame-00000000.jpg",
        "frame-00000010.jpg",
        "frame-00000029.jpg",
    ]
    assert all(type(frame) is RetainedVideoFrame for frame in frames)
    assert all(frame.path.parent == output_parent / "lecture" / "frames" for frame in frames)
    assert all(frame.path.is_file() for frame in frames)
    decoded_frames = [cv2.imread(str(frame.path)) for frame in frames]
    assert all(frame.shape[:2] == (48, 64) for frame in decoded_frames)
    decoded_means = [float(frame.mean()) for frame in decoded_frames]
    assert decoded_means[0] < 40.0
    assert decoded_means[1] > 200.0
    assert 50.0 < decoded_means[2] < 100.0

    with pytest.raises(FrozenInstanceError):
        frames[0].frame_index = 1  # type: ignore[misc]


def test_extract_video_frames_compares_and_retains_a_changed_final_frame(
    tmp_path: Path,
) -> None:
    source = _write_final_frame_change_mp4(tmp_path / "ending-change.mp4")

    frames = extract_video_frames(source, output_dir=tmp_path / "output")

    assert [frame.frame_index for frame in frames] == [0, 5]
    assert [frame.timestamp_seconds for frame in frames] == pytest.approx(
        [0.0, 2.5]
    )
    assert all(frame.path.is_file() for frame in frames)


def test_extract_video_frames_retains_equal_luma_color_changes(
    tmp_path: Path,
) -> None:
    source = _write_equal_luma_color_change_mp4(tmp_path / "color-slides.mp4")

    frames = extract_video_frames(source, output_dir=tmp_path / "output")

    assert [frame.frame_index for frame in frames] == [0, 10, 29]
    assert [frame.timestamp_seconds for frame in frames] == pytest.approx(
        [0.0, 5.0, 14.5]
    )


def test_extract_video_frames_uses_vfr_container_time_and_frame_pts(
    tmp_path: Path,
) -> None:
    import cv2

    source = _write_variable_frame_rate_mp4(tmp_path / "variable.mp4")

    info = inspect_video(source)
    frames = extract_video_frames(source, output_dir=tmp_path / "output")

    assert info.frame_count == 5
    assert info.duration_seconds == pytest.approx(4.56, abs=0.08)
    assert [frame.frame_index for frame in frames] == [0, 4]
    assert [frame.timestamp_seconds for frame in frames] == pytest.approx(
        [0.0, 4.52],
        abs=0.02,
    )
    retained = [cv2.imread(str(frame.path)) for frame in frames]
    assert all(frame is not None for frame in retained)
    assert [float(frame.mean()) for frame in retained] == pytest.approx(
        [20.0, 230.0],
        abs=10.0,
    )


def test_extract_video_frames_applies_mp4_display_rotation(tmp_path: Path) -> None:
    import cv2

    source = _write_rotated_display_mp4(tmp_path / "phone.mp4")

    info = inspect_video(source)
    frames = extract_video_frames(source, output_dir=tmp_path / "output")

    assert (info.width_pixels, info.height_pixels) == (64, 96)
    assert [frame.frame_index for frame in frames] == [1]
    retained = cv2.imread(str(frames[0].path))
    assert retained.shape[:2] == (96, 64)
    assert retained[12, 52, 0] > 220
    assert retained[84, 12, 2] > 220


def test_video_frame_scan_counts_the_final_frame_before_decoding() -> None:
    from ocrllm.video.scan_video_frame_candidates import scan_video_frame_candidates

    with pytest.raises(VideoError) as captured:
        scan_video_frame_candidates(
            Path("must-not-open.mp4"),
            video_info=VideoInfo(
                frame_count=49_997,
                frames_per_second=1.0,
                duration_seconds=49_997.0,
                width_pixels=64,
                height_pixels=48,
            ),
            cv2=None,
        )

    assert captured.value.code == "VIDEO_INVALID"
    assert captured.value.details["maximum_candidate_count"] == 10_000


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
                luminance_thumbnail=thumbnail,
                color_thumbnail=np.repeat(thumbnail[:, :, None], 3, axis=2),
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
            luminance_thumbnail=np.full(
                (128, 128),
                255 if index % 2 else 0,
                dtype=np.uint8,
            ),
            color_thumbnail=np.full(
                (32, 32, 3),
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


def test_extract_video_frames_maximum_segment_rounds_up() -> None:
    import cv2
    import numpy as np

    from ocrllm.video.select_video_frame_candidates import select_video_frame_candidates
    from ocrllm.video.video_frame_candidate import VideoFrameCandidate

    black = np.zeros((128, 128), dtype=np.uint8)
    white = np.full((128, 128), 255, dtype=np.uint8)
    candidates = []
    for index in range(181):
        if index <= 5:
            thumbnail = white if index % 2 else black
        elif index < 40:
            thumbnail = white
        else:
            thumbnail = black
        candidates.append(
            VideoFrameCandidate(
                frame_index=index,
                timestamp_seconds=float(index * 5),
                luminance_thumbnail=thumbnail,
                color_thumbnail=np.repeat(thumbnail[:, :, None], 3, axis=2),
            )
        )

    selected = select_video_frame_candidates(
        tuple(candidates),
        duration_seconds=900.0,
        cv2=cv2,
    )

    timestamps = (0.0,) + tuple(
        candidate.timestamp_seconds for candidate in selected
    )
    assert max(
        timestamps[index + 1] - timestamps[index]
        for index in range(len(timestamps) - 1)
    ) <= 315.0


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


@pytest.mark.skipif(os.name != "nt", reason="Windows legacy path-limit regression")
def test_extract_video_frames_caps_supplementary_unicode_stem_units(
    tmp_path: Path,
) -> None:
    if _windows_path_units(tmp_path) >= 130:
        pytest.skip("pytest temporary root is already beyond the controlled path range")
    unicode_stem = "😀" * 60
    source = _write_sectioned_mp4(tmp_path / f"{unicode_stem}.mp4")
    output_parent = _make_directory_with_windows_path_units(tmp_path / "out", 130)

    frames = extract_video_frames(source, output_dir=output_parent)

    expected_stem = "😀" * 48
    created_paths = (
        output_parent / expected_stem,
        output_parent / expected_stem / "frames",
        *(frame.path for frame in frames),
    )
    assert max(_windows_path_units(path) for path in created_paths) <= 259
    assert all(path.exists() for path in created_paths)
