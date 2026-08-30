"""Public contract for extracting and independently recognizing video audio."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ocrllm import (
    DependencyMissing,
    OutputError,
    OutputExists,
    VideoError,
    extract_video_audio,
)
from ocrllm.audio.probe_short_mp3 import probe_short_mp3

from write_test_image import write_test_image


def _ffmpeg_executable() -> Path:
    import imageio_ffmpeg

    return Path(imageio_ffmpeg.get_ffmpeg_exe())


def _write_mp4_with_audio(path: Path, *, frequency_hz: int = 440) -> Path:
    completed = subprocess.run(
        [
            str(_ffmpeg_executable()),
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=64x48:r=2:d=1",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency_hz}:sample_rate=16000:duration=1",
            "-shortest",
            "-c:v",
            "mpeg4",
            "-c:a",
            "aac",
            str(path),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert completed.returncode == 0
    return path


def _estimate_mp3_frequency(path: Path) -> float:
    import miniaudio

    decoded = miniaudio.decode_file(
        str(path),
        output_format=miniaudio.SampleFormat.SIGNED16,
        nchannels=1,
        sample_rate=16000,
    )
    samples = decoded.samples
    start = min(1600, len(samples))
    stop = min(14400, len(samples))
    assert stop > start
    crossings = sum(
        (samples[index - 1] <= 0 < samples[index])
        or (samples[index - 1] >= 0 > samples[index])
        for index in range(start + 1, stop)
    )
    return crossings * 16000.0 / (2.0 * (stop - start))


def _write_silent_mp4(path: Path) -> Path:
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
        for value in (20, 80, 140, 200):
            writer.write(np.full((48, 64, 3), value, dtype=np.uint8))
    finally:
        writer.release()
    return path


def test_extract_video_audio_publishes_valid_mono_mp3_atomically(
    tmp_path: Path,
) -> None:
    import miniaudio

    source = _write_mp4_with_audio(tmp_path / "lecture.mp4")
    output_parent = tmp_path / "output"
    output_parent.mkdir()
    output_path = output_parent / "audio.mp3"

    extracted = extract_video_audio(source, output_path=output_path)

    assert extracted == output_path
    assert extracted.is_file()
    assert extracted.stat().st_size > 0
    assert probe_short_mp3(extracted) == pytest.approx(1.0, abs=0.1)
    info = miniaudio.mp3_get_file_info(str(extracted))
    assert info.nchannels == 1
    assert info.sample_rate == 16000
    assert not list(output_parent.glob(".ocrllm-audio-*"))


def test_extract_video_audio_uses_one_snapshot_if_caller_path_is_replaced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_mp4_with_audio(
        tmp_path / "source.mp4",
        frequency_hz=440,
    )
    original_bytes = source.read_bytes()
    replacement = _write_mp4_with_audio(
        tmp_path / "replacement.mp4",
        frequency_hz=880,
    )
    replacement_bytes = replacement.read_bytes()
    output_parent = tmp_path / "output"
    output_parent.mkdir()
    output_path = output_parent / "audio.mp3"
    module = __import__("ocrllm.video.extract_video_audio", fromlist=["unused"])
    real_inspect = module.inspect_video
    inspected_paths: list[Path] = []

    def inspect_then_replace(snapshot_path: Path):
        info = real_inspect(snapshot_path)
        inspected_paths.append(snapshot_path)
        assert snapshot_path.read_bytes() == original_bytes
        replacement.replace(source)
        return info

    monkeypatch.setattr(module, "inspect_video", inspect_then_replace)

    extracted = extract_video_audio(source, output_path=output_path)

    assert extracted == output_path
    assert source.read_bytes() == replacement_bytes
    assert len(inspected_paths) == 1
    assert inspected_paths[0] != source
    assert not inspected_paths[0].exists()
    assert _estimate_mp3_frequency(extracted) == pytest.approx(440.0, abs=10.0)
    assert not list(output_parent.glob(".ocrllm-video-source-*"))
    assert not list(output_parent.glob(".ocrllm-audio-*"))


def test_extract_video_audio_rejects_video_without_audio_and_cleans_staging(
    tmp_path: Path,
) -> None:
    source = _write_silent_mp4(tmp_path / "silent.mp4")
    output_parent = tmp_path / "output"
    output_parent.mkdir()
    retained_frame = write_test_image(output_parent / "frames" / "frame.jpg")
    output_path = output_parent / "audio.mp3"

    with pytest.raises(VideoError) as captured:
        extract_video_audio(source, output_path=output_path)

    assert captured.value.code == "VIDEO_NO_AUDIO_STREAM"
    assert captured.value.details == {"stage": "audio_stream_probe"}
    assert not output_path.exists()
    assert not list(output_parent.glob(".ocrllm-audio-*"))
    assert retained_frame.is_file()


def test_audio_stream_probe_keeps_nonabsence_failures_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_silent_mp4(tmp_path / "source.mp4")
    output_path = tmp_path / "audio.mp3"
    module = __import__("ocrllm.video.extract_video_audio", fromlist=["unused"])
    calls: list[list[str]] = []

    def fail_required_and_optional(*args, **kwargs):
        calls.append(args[0])
        return subprocess.CompletedProcess(args[0], 1)

    monkeypatch.setattr(module.subprocess, "run", fail_required_and_optional)

    with pytest.raises(VideoError) as captured:
        extract_video_audio(source, output_path=output_path)

    assert captured.value.code == "VIDEO_INVALID"
    assert captured.value.details == {"stage": "audio_stream_probe"}
    assert len(calls) == 2
    assert "-xerror" in calls[0]
    assert "-frames:a" in calls[0]
    assert "0:a:0" in calls[0]
    assert "0:a:0?" in calls[1]
    assert not output_path.exists()
    assert not list(tmp_path.glob(".ocrllm-audio-*"))


def test_present_but_corrupt_audio_is_not_reported_as_missing(
    tmp_path: Path,
) -> None:
    valid_source = _write_mp4_with_audio(tmp_path / "valid.mp4")
    source = tmp_path / "corrupt.mp4"
    completed = subprocess.run(
        [
            str(_ffmpeg_executable()),
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(valid_source),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-c",
            "copy",
            "-bsf:a",
            "noise=amount=1",
            "-movflags",
            "+faststart",
            str(source),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert completed.returncode == 0
    output_path = tmp_path / "audio.mp3"

    with pytest.raises(VideoError) as captured:
        extract_video_audio(source, output_path=output_path)

    assert captured.value.code == "VIDEO_INVALID"
    assert captured.value.details == {"stage": "extraction"}
    assert not output_path.exists()
    assert not list(tmp_path.glob(".ocrllm-audio-*"))


def test_extract_video_audio_rejects_existing_target_before_backend_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "audio.mp3"
    target.write_bytes(b"caller-owned")

    def forbidden_inspection(source):
        raise AssertionError("video inspection must not start")

    module = __import__("ocrllm.video.extract_video_audio", fromlist=["unused"])
    monkeypatch.setattr(module, "inspect_video", forbidden_inspection)

    with pytest.raises(OutputExists):
        extract_video_audio(tmp_path / "not-opened.mp4", output_path=target)

    assert target.read_bytes() == b"caller-owned"


def test_extract_video_audio_requires_existing_plain_output_parent(
    tmp_path: Path,
) -> None:
    source = tmp_path / "not-opened.mp4"

    with pytest.raises(OutputError) as captured:
        extract_video_audio(
            source,
            output_path=tmp_path / "missing" / "audio.mp3",
        )

    assert captured.value.code == "OUTPUT_PATH_INVALID"
    assert not (tmp_path / "missing").exists()


def test_extract_video_audio_timeout_leaves_no_output_or_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_silent_mp4(tmp_path / "source.mp4")
    output_path = tmp_path / "audio.mp3"
    module = __import__("ocrllm.video.extract_video_audio", fromlist=["unused"])

    def time_out(*args, **kwargs):
        raise subprocess.TimeoutExpired("ffmpeg", timeout=600)

    monkeypatch.setattr(module.subprocess, "run", time_out)

    with pytest.raises(VideoError) as captured:
        extract_video_audio(source, output_path=output_path)

    assert captured.value.code == "VIDEO_INVALID"
    assert not output_path.exists()
    assert not list(tmp_path.glob(".ocrllm-audio-*"))


def test_extract_video_audio_rejects_invalid_success_output_before_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_mp4_with_audio(tmp_path / "source.mp4")
    output_path = tmp_path / "audio.mp3"
    module = __import__("ocrllm.video.extract_video_audio", fromlist=["unused"])
    calls = 0

    def fake_ffmpeg(executable, arguments, *, stage):
        nonlocal calls
        calls += 1
        if stage == "extraction":
            Path(arguments[-1]).write_bytes(b"not an MP3")
            return
        raise VideoError(
            "The extracted video audio is invalid.",
            code="VIDEO_INVALID",
            details={"stage": stage},
        )

    monkeypatch.setattr(module, "_run_ffmpeg", fake_ffmpeg)

    with pytest.raises(VideoError) as captured:
        extract_video_audio(source, output_path=output_path)

    assert captured.value.details == {"stage": "validation"}
    assert calls == 2
    assert not output_path.exists()
    assert not list(tmp_path.glob(".ocrllm-audio-*"))


def test_video_audio_backend_reports_missing_optional_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    loader = __import__("ocrllm.video.load_imageio_ffmpeg", fromlist=["unused"])
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)

    with pytest.raises(DependencyMissing) as captured:
        loader.load_imageio_ffmpeg_executable()

    assert captured.value.details == {"extra": "video"}
