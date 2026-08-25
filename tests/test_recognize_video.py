"""Public orchestration contract for independently recognized video media."""

from __future__ import annotations

from contextlib import contextmanager
import os
import subprocess
from pathlib import Path
from threading import Event

import pytest

from ocrllm import (
    AudioModelSettings,
    Cancelled,
    Config,
    ConfigError,
    GoogleGenAISettings,
    OutputError,
    ProviderError,
    RecognitionExecutionPolicy,
    VideoRecognitionOutcome,
    VisionModelSettings,
    compose_video_result,
    publish_video_result,
    recognize_video,
)
from ocrllm.providers.google_genai.google_genai_audio_response import (
    GoogleGenAIAudioResponse,
)
from ocrllm.providers.vision_provider_response import VisionProviderResponse


def _ffmpeg_executable() -> Path:
    import imageio_ffmpeg

    return Path(imageio_ffmpeg.get_ffmpeg_exe())


def _write_mp4(
    path: Path,
    *,
    with_audio: bool = True,
    color: str = "blue",
    frequency: int = 440,
) -> Path:
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
        f"color=c={color}:s=64x48:r=2:d=1",
    ]
    if with_audio:
        command.extend(
            (
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={frequency}:sample_rate=16000:duration=1",
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


def _write_multiscene_mp4(path: Path) -> Path:
    import cv2
    import numpy as np

    silent_path = path.with_name(f"{path.stem}-silent.mp4")
    writer = cv2.VideoWriter(
        str(silent_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        1.0,
        (64, 48),
    )
    assert writer.isOpened()
    try:
        for index in range(60):
            value = (20 + (index // 5) * 30) % 256
            writer.write(np.full((48, 64, 3), value, dtype=np.uint8))
    finally:
        writer.release()

    command = [
        str(_ffmpeg_executable()),
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(silent_path),
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=16000:duration=60",
        "-shortest",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    finally:
        silent_path.unlink(missing_ok=True)
    assert completed.returncode == 0
    return path


def _write_corrupt_audio_mp4(path: Path) -> Path:
    valid_source = _write_mp4(path.with_name(f"valid-{path.name}"))
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


class _ImageProvider:
    def __init__(
        self,
        *,
        fail_on_call: int | None = None,
        failure_code: str = "PROVIDER_RESPONSE_INVALID",
    ) -> None:
        self.fail_on_call = fail_on_call
        self.failure_code = failure_code
        self.calls: list[tuple[Path, ...]] = []

    def recognize_images(self, image_paths, *, prompt, config):
        self.calls.append(tuple(image_paths))
        if len(self.calls) == self.fail_on_call:
            raise ProviderError("Image provider failed.", code=self.failure_code)
        return "# Frames\n"


def test_recognize_video_uses_one_snapshot_for_frames_and_audio_after_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib

    prepare = importlib.import_module("ocrllm.video.prepare_video_media")
    audio_extractor = importlib.import_module("ocrllm.video.extract_video_audio")
    source = _write_mp4(
        tmp_path / "lecture.mp4",
        color="blue",
        frequency=440,
    )
    replacement = _write_mp4(
        tmp_path / "replacement.mp4",
        color="red",
        frequency=880,
    )
    original_bytes = source.read_bytes()
    replacement_bytes = replacement.read_bytes()
    assert original_bytes != replacement_bytes
    real_scan = prepare.scan_video_frame_candidates
    real_extract_audio = audio_extractor._extract_video_audio_from_stable_source
    observed_audio_sources: list[Path] = []

    def scan_then_replace(snapshot_path, *, video_info, cv2):
        candidates = real_scan(snapshot_path, video_info=video_info, cv2=cv2)
        replacement.replace(source)
        return candidates

    def observe_audio_source(snapshot_path, *, output_path):
        observed_audio_sources.append(snapshot_path)
        assert snapshot_path != source
        assert snapshot_path.read_bytes() == original_bytes
        return real_extract_audio(snapshot_path, output_path=output_path)

    monkeypatch.setattr(prepare, "scan_video_frame_candidates", scan_then_replace)
    monkeypatch.setattr(
        audio_extractor,
        "_extract_video_audio_from_stable_source",
        observe_audio_source,
    )
    observed_audio_snapshots = _install_fake_audio(monkeypatch)
    image_provider = _ImageProvider()

    outcome = recognize_video(
        source,
        output_dir=tmp_path / "output",
        image_config=Config(provider=image_provider),
        audio_config=_audio_config(tmp_path),
    )

    assert outcome.status == "complete"
    assert source.read_bytes() == replacement_bytes
    assert len(observed_audio_sources) == 1
    assert not observed_audio_sources[0].exists()
    assert len(observed_audio_snapshots) == 1
    assert not observed_audio_snapshots[0].exists()
    assert all(frame.path.is_file() for frame in outcome.retained_frames)
    assert outcome.audio_artifact is not None and outcome.audio_artifact.is_file()
    assert not list((tmp_path / "output").glob(".ocrllm-video-source-*"))


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


def _install_fake_google_image(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fail_on_call: int | None = None,
) -> list[tuple[Path, ...]]:
    observed: list[tuple[Path, ...]] = []

    def fake_google_image(image_paths, *, prompt, config):
        observed.append(tuple(image_paths))
        if len(observed) == fail_on_call:
            raise ProviderError("Image provider failed.")
        return VisionProviderResponse(
            markdown="# Frames\n",
            input_tokens=11,
            output_tokens=3,
        )

    adapter = __import__(
        "ocrllm.providers.google_genai.recognize_images",
        fromlist=["unused"],
    )
    monkeypatch.setattr(adapter, "recognize_images", fake_google_image)
    return observed


def _observe_request_owned_video_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> list[Path]:
    import importlib

    prepare = importlib.import_module("ocrllm.video.prepare_video_media")
    real_snapshot = prepare.snapshot_video_source
    observed: list[Path] = []

    @contextmanager
    def observe_snapshot(source_path, *, snapshot_parent):
        with real_snapshot(
            source_path,
            snapshot_parent=snapshot_parent,
        ) as snapshot_path:
            assert snapshot_path.is_file()
            observed.append(snapshot_path)
            yield snapshot_path

    monkeypatch.setattr(prepare, "snapshot_video_source", observe_snapshot)
    return observed


def test_image_cancellation_exit_removes_video_snapshot_and_releases_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ocrllm.output.claim_output_target import claim_output_target

    source = _write_mp4(tmp_path / "lecture.mp4")
    cancellation = Event()
    cancellation.set()
    image_provider = _ImageProvider()
    _install_fake_audio(monkeypatch)
    video_snapshots = _observe_request_owned_video_snapshot(monkeypatch)
    outcome = None
    cancellation_raised = False

    try:
        outcome = recognize_video(
            source,
            output_dir=tmp_path / "output",
            image_config=Config(
                provider=image_provider,
                cancellation=cancellation,
            ),
            audio_config=_audio_config(tmp_path),
        )
    except Cancelled:
        cancellation_raised = True

    cancellation_returned = outcome is not None and any(
        isinstance(item.error, Cancelled) for item in outcome.frame_outcomes
    )
    assert cancellation_raised or cancellation_returned
    assert image_provider.calls == []
    assert len(video_snapshots) == 1
    assert not video_snapshots[0].exists()
    assert not list((tmp_path / "output").glob(".ocrllm-video-source-*"))
    with claim_output_target(tmp_path / "output" / "lecture"):
        pass


def test_audio_cancellation_exit_removes_video_snapshot_and_releases_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ocrllm.output.claim_output_target import claim_output_target

    source = _write_mp4(tmp_path / "lecture.mp4")
    cancellation = Event()
    cancellation.set()
    image_provider = _ImageProvider()
    observed_audio = _install_fake_audio(monkeypatch)
    video_snapshots = _observe_request_owned_video_snapshot(monkeypatch)
    outcome = None
    cancellation_raised = False

    try:
        outcome = recognize_video(
            source,
            output_dir=tmp_path / "output",
            image_config=Config(provider=image_provider),
            audio_config=Config(
                provider=GoogleGenAISettings(api_key="test-only-google-key"),
                audio_model=AudioModelSettings(name="test-audio-model"),
                temp_dir=tmp_path / "audio-snapshots",
                cancellation=cancellation,
            ),
        )
    except Cancelled:
        cancellation_raised = True

    cancellation_returned = (
        outcome is not None and isinstance(outcome.audio_error, Cancelled)
    )
    assert cancellation_raised or cancellation_returned
    assert observed_audio == []
    assert len(video_snapshots) == 1
    assert not video_snapshots[0].exists()
    assert not list((tmp_path / "output").glob(".ocrllm-video-source-*"))
    with claim_output_target(tmp_path / "output" / "lecture"):
        pass


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


@pytest.mark.skipif(os.name != "nt", reason="Windows Unicode path regression")
def test_recognize_video_keeps_separate_providers_on_unicode_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ascii_source = _write_mp4(tmp_path / "source.mp4")
    source_parent = tmp_path / "\u8bfe\u7a0b\u8d44\u6599"
    source_parent.mkdir()
    source = ascii_source.replace(source_parent / "\u8bb2\u5ea7\u89c6\u9891.mp4")
    output_parent = tmp_path / "\u8bc6\u522b\u8f93\u51fa"
    image_temp = tmp_path / "\u56fe\u7247\u8bf7\u6c42\u7f13\u5b58"
    audio_temp = tmp_path / "\u97f3\u9891\u8bf7\u6c42\u7f13\u5b58"
    image_provider = _ImageProvider()
    observed_audio = _install_fake_audio(monkeypatch)

    outcome = recognize_video(
        source,
        output_dir=output_parent,
        image_config=Config(
            provider=image_provider,
            temp_dir=image_temp,
        ),
        audio_config=Config(
            provider=GoogleGenAISettings(api_key="test-only-google-key"),
            audio_model=AudioModelSettings(name="test-audio-model"),
            temp_dir=audio_temp,
        ),
    )

    assert outcome.status == "complete"
    assert [frame.frame_index for frame in outcome.retained_frames] == [1]
    assert outcome.output_root == output_parent / "\u8bb2\u5ea7\u89c6\u9891"
    assert [frame.path.name for frame in outcome.retained_frames] == [
        "frame-00000001.jpg"
    ]
    assert all(frame.path.is_file() for frame in outcome.retained_frames)
    assert outcome.audio_artifact == outcome.output_root / "audio.mp3"
    assert outcome.audio_artifact.is_file()
    assert len(image_provider.calls) == 1
    assert all(image_temp in path.parents for path in image_provider.calls[0])
    assert len(observed_audio) == 1
    assert audio_temp in observed_audio[0].parents
    assert all(not path.exists() for path in image_provider.calls[0])
    assert not observed_audio[0].exists()
    assert not any(image_temp.rglob("*"))
    assert not any(audio_temp.rglob("*"))
    assert not list(outcome.output_root.glob(".ocrllm-audio-*"))

    target = output_parent / "\u6700\u7ec8\u8bc6\u522b\u7ed3\u679c.md"
    published = publish_video_result(outcome, target)
    assert published.status == "complete"
    assert published.output_path == target
    assert target.read_text(encoding="utf-8") == published.markdown
    assert published.assets == tuple(
        frame.path for frame in outcome.retained_frames
    ) + (outcome.audio_artifact,)
    assert published.metadata["current_run_provider_call_count"] == 2
    assert not list(output_parent.glob(".ocrllm-*.tmp"))


def test_recognize_video_keeps_real_multigroup_order_and_separate_audio(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_multiscene_mp4(tmp_path / "lecture.mp4")
    observed_images = _install_fake_google_image(monkeypatch)
    observed_audio = _install_fake_audio(monkeypatch)

    outcome = recognize_video(
        source,
        output_dir=tmp_path / "output",
        image_config=Config(
            provider=GoogleGenAISettings(api_key="test-only-google-key"),
            vision_model=VisionModelSettings(name="test-image-model"),
            temp_dir=tmp_path / "image-snapshots",
        ),
        audio_config=_audio_config(tmp_path),
    )

    retained_indices = tuple(
        frame.frame_index for frame in outcome.retained_frames
    )
    assert retained_indices == (0, 5, 10, 20, 25, 30, 35, 45, 50, 59)
    assert [len(call) for call in observed_images] == [8, 2]
    provider_paths = tuple(
        path for call in observed_images for path in call
    )
    assert tuple(path.name for path in provider_paths) == tuple(
        frame.path.name for frame in outcome.retained_frames
    )
    assert all(not path.exists() for path in provider_paths)
    assert [item.index for item in outcome.frame_outcomes] == [0, 1]
    assert all(item.succeeded for item in outcome.frame_outcomes)
    assert len(observed_audio) == 1
    assert not observed_audio[0].exists()
    assert outcome.status == "complete"

    composed = compose_video_result(outcome)
    assert composed.status == "complete"
    assert composed.metadata["current_run_provider_call_count"] == 3
    assert composed.metadata["current_model_token_usage"] == (
        {
            "model": "test-image-model",
            "input_tokens": 22,
            "output_tokens": 6,
        },
        {
            "model": "test-audio-model",
            "input_tokens": 7,
            "output_tokens": 2,
        },
    )


def test_recognize_video_preserves_settled_work_after_later_group_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_multiscene_mp4(tmp_path / "lecture.mp4")
    observed_images = _install_fake_google_image(monkeypatch, fail_on_call=2)
    observed_audio = _install_fake_audio(monkeypatch)

    outcome = recognize_video(
        source,
        output_dir=tmp_path / "output",
        image_config=Config(
            provider=GoogleGenAISettings(api_key="test-only-google-key"),
            vision_model=VisionModelSettings(name="test-image-model"),
            execution=RecognitionExecutionPolicy(maximum_images_per_request=3),
            temp_dir=tmp_path / "image-snapshots",
        ),
        audio_config=_audio_config(tmp_path),
    )

    assert [len(call) for call in observed_images] == [3, 3]
    assert all(not path.exists() for call in observed_images for path in call)
    assert [item.index for item in outcome.frame_outcomes] == [0, 1, 2, 3]
    assert outcome.frame_outcomes[0].succeeded
    assert isinstance(outcome.frame_outcomes[1].error, ProviderError)
    assert isinstance(outcome.frame_outcomes[2].error, Cancelled)
    assert isinstance(outcome.frame_outcomes[3].error, Cancelled)
    assert (
        outcome.frame_outcomes[1].error.details["provider_calls_attempted"] == 1
    )
    assert "provider_calls_attempted" not in outcome.frame_outcomes[2].error.details
    assert "provider_calls_attempted" not in outcome.frame_outcomes[3].error.details
    assert len(observed_audio) == 1
    assert not observed_audio[0].exists()
    assert outcome.audio_result is not None
    assert outcome.audio_artifact is not None
    assert outcome.audio_artifact.is_file()
    assert all(frame.path.is_file() for frame in outcome.retained_frames)
    assert outcome.status == "partial"

    composed = compose_video_result(outcome)
    assert composed.status == "partial"
    assert composed.assets == tuple(
        frame.path for frame in outcome.retained_frames
    ) + (outcome.audio_artifact,)
    assert composed.metadata["successful_video_frame_group_count"] == 1
    assert composed.metadata["failed_video_frame_group_count"] == 3
    assert composed.metadata["current_run_provider_call_count"] is None
    assert composed.metadata["current_model_token_usage"] == (
        {
            "model": "test-image-model",
            "input_tokens": 11,
            "output_tokens": 3,
        },
        {
            "model": "test-audio-model",
            "input_tokens": 7,
            "output_tokens": 2,
        },
    )


def test_video_publication_preserves_audio_after_frame_provider_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_mp4(tmp_path / "lecture.mp4")
    image_provider = _ImageProvider(
        fail_on_call=1,
        failure_code="PROVIDER_UNAVAILABLE",
    )
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
    assert all(item.error is not None for item in outcome.frame_outcomes)
    assert [item.error.code for item in outcome.frame_outcomes] == [
        "PROVIDER_UNAVAILABLE"
    ]
    assert [
        item.error.details["provider_calls_attempted"]
        for item in outcome.frame_outcomes
    ] == [1]
    assert len(image_provider.calls) == 1
    assert len(observed_audio) == 1
    assert outcome.audio_artifact is not None
    assert outcome.audio_artifact.is_file()

    target = tmp_path / "reports" / "lecture.md"
    published = publish_video_result(outcome, target)

    retained_identity = tuple(
        (frame.frame_index, frame.timestamp_seconds)
        for frame in outcome.retained_frames
    )
    assert published.status == "partial"
    assert published.output_path == target
    assert target.read_text(encoding="utf-8") == published.markdown
    assert "Recognition error: `PROVIDER_UNAVAILABLE`" in published.markdown
    assert "# Audio" in published.markdown
    assert "\n# Frames\n" not in published.markdown
    assert published.assets == tuple(
        frame.path for frame in outcome.retained_frames
    ) + (outcome.audio_artifact,)
    assert published.metadata["successful_video_frame_group_count"] == 0
    assert published.metadata["failed_video_frame_group_count"] == 1
    assert published.metadata["audio_state"] == "recognized"
    assert published.metadata["current_run_provider_call_count"] == 2
    assert published.metadata["current_model_token_usage"] == (
        {
            "model": "test-audio-model",
            "input_tokens": 7,
            "output_tokens": 2,
        },
    )
    assert published.metadata["video_frame_group_errors"] == (
        {
            "index": 0,
            "code": "PROVIDER_UNAVAILABLE",
            "frame_indices": tuple(index for index, _ in retained_identity),
            "frame_timestamps_seconds": tuple(
                timestamp for _, timestamp in retained_identity
            ),
        },
    )
    assert not list(target.parent.glob(".ocrllm-*.tmp"))


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


def test_recognize_video_keeps_image_branch_when_audio_is_corrupt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_corrupt_audio_mp4(tmp_path / "corrupt-audio.mp4")
    image_provider = _ImageProvider()
    observed_audio = _install_fake_audio(monkeypatch)

    outcome = recognize_video(
        source,
        output_dir=tmp_path / "output",
        image_config=Config(provider=image_provider),
        audio_config=_audio_config(tmp_path),
    )
    composed = compose_video_result(outcome)

    assert outcome.status == "partial"
    assert all(item.succeeded for item in outcome.frame_outcomes)
    assert len(image_provider.calls) == 1
    assert observed_audio == []
    assert outcome.audio_state == "failed"
    assert outcome.audio_error is not None
    assert outcome.audio_error.code == "VIDEO_INVALID"
    assert outcome.audio_error.details == {"stage": "extraction"}
    assert outcome.audio_artifact is None
    assert all(frame.path.is_file() for frame in outcome.retained_frames)
    assert not list(outcome.output_root.glob(".ocrllm-audio-*"))
    assert composed.status == "partial"
    assert composed.assets == tuple(frame.path for frame in outcome.retained_frames)
    assert composed.metadata["current_run_provider_call_count"] == 1


def test_recognize_video_is_failed_when_neither_provider_produces_a_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_mp4(tmp_path / "lecture.mp4")
    image_provider = _ImageProvider(fail_on_call=1)
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

    reserved_audio_path = outcome.output_root / "audio.mp3"
    retained_bytes = tuple(
        frame.path.read_bytes() for frame in outcome.retained_frames
    )
    with pytest.raises(OutputError) as captured:
        publish_video_result(outcome, reserved_audio_path)

    assert captured.value.code == "OUTPUT_PATH_INVALID"
    assert not reserved_audio_path.exists()
    assert tuple(
        frame.path.read_bytes() for frame in outcome.retained_frames
    ) == retained_bytes
    assert list(outcome.output_root.glob(".ocrllm-*.tmp")) == []


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


def test_recognize_video_rejects_invalid_audio_cancellation_before_source(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "output"

    with pytest.raises(ConfigError, match=r"callable is_set\(\)"):
        recognize_video(
            tmp_path / "not-opened.mp4",
            output_dir=output_dir,
            image_config=Config(provider=_ImageProvider()),
            audio_config=Config(
                provider=GoogleGenAISettings(api_key="test-only-google-key"),
                audio_model=AudioModelSettings(name="test-audio-model"),
                cancellation=object(),
            ),
        )

    assert not output_dir.exists()


def test_recognize_video_rejects_invalid_image_cancellation_before_source(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "output"

    with pytest.raises(ConfigError, match=r"callable is_set\(\)"):
        recognize_video(
            tmp_path / "not-opened.mp4",
            output_dir=output_dir,
            image_config=Config(
                provider=_ImageProvider(),
                cancellation=object(),
            ),
            audio_config=_audio_config(tmp_path),
        )

    assert not output_dir.exists()


def test_recognize_video_rejects_invalid_image_config_before_output_or_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_mp4(tmp_path / "lecture.mp4")
    observed_audio = _install_fake_audio(monkeypatch)
    output_dir = tmp_path / "output"

    with pytest.raises(ConfigError, match="explicit model"):
        recognize_video(
            source,
            output_dir=output_dir,
            image_config=Config(
                provider=GoogleGenAISettings(api_key="test-only-google-key"),
            ),
            audio_config=_audio_config(tmp_path),
        )

    assert observed_audio == []
    assert not output_dir.exists()


def test_recognize_video_rejects_noncallable_injected_image_provider_before_source(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "output"

    with pytest.raises(ConfigError, match="callable recognize_images"):
        recognize_video(
            tmp_path / "not-opened.mp4",
            output_dir=output_dir,
            image_config=Config(provider=object()),
            audio_config=_audio_config(tmp_path),
        )

    assert not output_dir.exists()
