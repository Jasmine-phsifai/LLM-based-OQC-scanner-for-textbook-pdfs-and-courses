"""Public orchestration contract for independently recognized video media."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ocrllm import (
    AudioModelSettings,
    Config,
    ConfigError,
    GoogleGenAISettings,
    ProviderError,
    VideoRecognitionOutcome,
    compose_video_result,
    recognize_video,
)
from ocrllm.providers.google_genai.google_genai_audio_response import (
    GoogleGenAIAudioResponse,
)


def _ffmpeg_executable() -> Path:
    import imageio_ffmpeg

    return Path(imageio_ffmpeg.get_ffmpeg_exe())


def _write_mp4(path: Path, *, with_audio: bool = True) -> Path:
    command = [
        str(_ffmpeg_executable()),
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:s=64x48:r=2:d=1",
    ]
    if with_audio:
        command.extend(
            (
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:sample_rate=16000:duration=1",
                "-shortest",
            )
        )
    command.extend(("-c:v", "mpeg4"))
    if with_audio:
        command.extend(("-c:a", "aac"))
    command.append(str(path))
    completed = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert completed.returncode == 0
    return path


class _ImageProvider:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[Path, ...]] = []

    def recognize_images(self, image_paths, *, prompt, config):
        self.calls.append(tuple(image_paths))
        if self.fail:
            raise ProviderError("Image provider failed.")
        return "# Frames\n"


def _audio_config(tmp_path: Path) -> Config:
    return Config(
        provider=GoogleGenAISettings(api_key="test-only-google-key"),
        audio_model=AudioModelSettings(name="test-audio-model"),
        temp_dir=tmp_path / "audio-snapshots",
    )


def _install_fake_audio(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fail: bool = False,
) -> list[Path]:
    observed: list[Path] = []

    def fake_google_audio(snapshot, *, prompt, config):
        observed.append(snapshot.path)
        if fail:
            raise ProviderError("Audio provider failed.")
        return GoogleGenAIAudioResponse(
            markdown="# Audio\n",
            input_tokens=7,
            output_tokens=2,
        )

    processor = __import__(
        "ocrllm.processors.recognize_short_mp3",
        fromlist=["unused"],
    )
    monkeypatch.setattr(processor, "recognize_short_mp3", fake_google_audio)
    return observed


def test_recognize_video_runs_real_media_and_keeps_providers_separate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_mp4(tmp_path / "lecture.mp4")
    image_provider = _ImageProvider()
    observed_audio = _install_fake_audio(monkeypatch)

    outcome = recognize_video(
        source,
        output_dir=tmp_path / "output",
        image_config=Config(provider=image_provider),
        audio_config=_audio_config(tmp_path),
    )

    assert type(outcome) is VideoRecognitionOutcome
    assert outcome.status == "complete"
    assert outcome.audio_state == "recognized"
    assert outcome.frame_error is None
    assert outcome.audio_error is None
    assert outcome.audio_result is not None
    assert outcome.audio_result.source_type == "audio"
    assert all(item.succeeded for item in outcome.frame_outcomes)
    assert len(image_provider.calls) == len(outcome.frame_outcomes)
    assert len(observed_audio) == 1
    assert outcome.output_root.is_dir()
    assert outcome.audio_artifact == outcome.output_root / "audio.mp3"
    assert outcome.audio_artifact.is_file()
    assert all(frame.path.is_file() for frame in outcome.retained_frames)
    assert not observed_audio[0].exists()

    composed = compose_video_result(outcome)
    assert composed.source_type == "video"
    assert composed.status == "complete"
    assert "# Video frames" in composed.markdown
    assert "# Video audio" in composed.markdown
    assert composed.assets == tuple(
        frame.path for frame in outcome.retained_frames
    ) + (outcome.audio_artifact,)
    assert composed.metadata["current_run_provider_call_count"] == 2


def test_recognize_video_preserves_audio_after_frame_provider_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_mp4(tmp_path / "lecture.mp4")
    image_provider = _ImageProvider(fail=True)
    observed_audio = _install_fake_audio(monkeypatch)

    outcome = recognize_video(
        source,
        output_dir=tmp_path / "output",
        image_config=Config(provider=image_provider),
        audio_config=_audio_config(tmp_path),
    )

    assert outcome.status == "partial"
    assert outcome.audio_state == "recognized"
    assert outcome.audio_result is not None
    assert any(item.error is not None for item in outcome.frame_outcomes)
    assert len(image_provider.calls) == 1
    assert len(observed_audio) == 1
    assert outcome.audio_artifact is not None
    assert outcome.audio_artifact.is_file()


def test_recognize_video_preserves_frames_and_audio_artifact_on_audio_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_mp4(tmp_path / "lecture.mp4")
    image_provider = _ImageProvider()
    observed_audio = _install_fake_audio(monkeypatch, fail=True)

    outcome = recognize_video(
        source,
        output_dir=tmp_path / "output",
        image_config=Config(provider=image_provider),
        audio_config=_audio_config(tmp_path),
    )

    assert outcome.status == "partial"
    assert outcome.audio_state == "failed"
    assert outcome.audio_result is None
    assert outcome.audio_error is not None
    assert outcome.audio_error.code == "PROVIDER_RESPONSE_INVALID"
    assert all(item.succeeded for item in outcome.frame_outcomes)
    assert len(observed_audio) == 1
    assert outcome.audio_artifact is not None
    assert outcome.audio_artifact.is_file()
    assert all(frame.path.is_file() for frame in outcome.retained_frames)


def test_recognize_video_is_failed_when_neither_provider_produces_a_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_mp4(tmp_path / "lecture.mp4")
    image_provider = _ImageProvider(fail=True)
    observed_audio = _install_fake_audio(monkeypatch, fail=True)

    outcome = recognize_video(
        source,
        output_dir=tmp_path / "output",
        image_config=Config(provider=image_provider),
        audio_config=_audio_config(tmp_path),
    )

    assert outcome.status == "failed"
    assert outcome.audio_state == "failed"
    assert all(item.error is not None for item in outcome.frame_outcomes)
    assert outcome.audio_error is not None
    assert len(image_provider.calls) == 1
    assert len(observed_audio) == 1


def test_recognize_video_treats_only_missing_stream_as_absent_audio(
    tmp_path: Path,
) -> None:
    source = _write_mp4(tmp_path / "silent.mp4", with_audio=False)
    image_provider = _ImageProvider()

    outcome = recognize_video(
        source,
        output_dir=tmp_path / "output",
        image_config=Config(provider=image_provider),
        audio_config=_audio_config(tmp_path),
    )

    assert outcome.status == "complete"
    assert outcome.audio_state == "absent"
    assert outcome.audio_result is None
    assert outcome.audio_error is not None
    assert outcome.audio_error.code == "VIDEO_NO_AUDIO_STREAM"
    assert outcome.audio_artifact is None
    assert all(item.succeeded for item in outcome.frame_outcomes)
    assert len(image_provider.calls) == 1


def test_recognize_video_rejects_invalid_audio_config_before_output_or_dispatch(
    tmp_path: Path,
) -> None:
    source = tmp_path / "not-opened.mp4"
    image_provider = _ImageProvider()
    output_dir = tmp_path / "output"

    with pytest.raises(ConfigError):
        recognize_video(
            source,
            output_dir=output_dir,
            image_config=Config(provider=image_provider),
            audio_config=Config(provider=image_provider),
        )

    assert image_provider.calls == []
    assert not output_dir.exists()
