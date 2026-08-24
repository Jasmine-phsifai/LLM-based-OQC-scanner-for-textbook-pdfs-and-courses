"""Public contract for extracting and independently recognizing video audio."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ocrllm import (
    AudioModelSettings,
    Config,
    DependencyMissing,
    GoogleGenAISettings,
    OutputError,
    OutputExists,
    RetainedVideoFrame,
    VideoError,
    extract_video_audio,
    recognize,
    recognize_video_frames,
)
from ocrllm.audio.probe_short_mp3 import probe_short_mp3
from ocrllm.providers.google_genai.google_genai_audio_response import (
    GoogleGenAIAudioResponse,
)

from write_test_image import write_test_image


def _ffmpeg_executable() -> Path:
    import imageio_ffmpeg

    return Path(imageio_ffmpeg.get_ffmpeg_exe())


def _write_mp4_with_audio(path: Path) -> Path:
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
            "sine=frequency=440:sample_rate=16000:duration=1",
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

    assert captured.value.code == "VIDEO_INVALID"
    assert not output_path.exists()
    assert not list(output_parent.glob(".ocrllm-audio-*"))
    assert retained_frame.is_file()


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
    source = _write_silent_mp4(tmp_path / "source.mp4")
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


def test_video_frames_and_audio_use_independent_provider_configs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_mp4_with_audio(tmp_path / "lecture.mp4")
    audio_path = extract_video_audio(source, output_path=tmp_path / "audio.mp3")
    frame_path = write_test_image(tmp_path / "frame.jpg")
    frames = (RetainedVideoFrame(0, 0.0, frame_path),)

    class ImageProvider:
        def __init__(self) -> None:
            self.calls: list[tuple[Path, ...]] = []

        def recognize_images(self, image_paths, *, prompt, config):
            self.calls.append(tuple(image_paths))
            return "# Frame transcript\n"

    image_provider = ImageProvider()
    observed_audio: dict[str, object] = {}

    def fake_google_audio(snapshot, *, prompt, config):
        observed_audio["path"] = snapshot.path
        observed_audio["provider"] = config.provider
        return GoogleGenAIAudioResponse(
            markdown="# Audio transcript\n",
            input_tokens=12,
            output_tokens=3,
        )

    processor = __import__(
        "ocrllm.processors.recognize_short_mp3",
        fromlist=["unused"],
    )
    monkeypatch.setattr(processor, "recognize_short_mp3", fake_google_audio)

    frame_outcomes = recognize_video_frames(
        frames,
        config=Config(provider=image_provider),
    )
    audio_result = recognize(
        audio_path,
        config=Config(
            provider=GoogleGenAISettings(api_key="test-only-google-key"),
            audio_model=AudioModelSettings(name="test-audio-model"),
            temp_dir=tmp_path / "snapshots",
        ),
    )

    assert frame_outcomes[0].succeeded
    assert len(image_provider.calls) == 1
    observed_frame_path = image_provider.calls[0][0]
    assert observed_frame_path.name == frame_path.name
    assert observed_frame_path.suffix == ".jpg"
    assert not observed_frame_path.exists()
    assert audio_result.source_type == "audio"
    assert audio_result.metadata["provider"] == "google"
    assert type(observed_audio["provider"]) is GoogleGenAISettings
    assert Path(observed_audio["path"]).name == "source.mp3"
    assert not Path(observed_audio["path"]).exists()
    assert not tuple((tmp_path / "snapshots").iterdir())
