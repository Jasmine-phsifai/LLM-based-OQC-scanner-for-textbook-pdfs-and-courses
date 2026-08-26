"""Video-owned long-audio state and cleanup regressions."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from ocrllm import AudioModelSettings, Config, GoogleGenAISettings, OutputError
from ocrllm.processor_output import ProcessorOutput
from ocrllm.processors.recognize_video_mp3 import recognize_video_mp3


def _config(tmp_path: Path) -> Config:
    return Config(
        provider=GoogleGenAISettings(api_key="test-only-google-key"),
        audio_model=AudioModelSettings(name="test-audio-model"),
        temp_dir=tmp_path / "snapshots",
    )


def _snapshot(tmp_path: Path):
    path = tmp_path / "owned.mp3"
    path.write_bytes(b"owned-audio")
    return SimpleNamespace(
        path=path,
        byte_size=path.stat().st_size,
        sha256="a" * 64,
        duration_seconds=301.0,
    )


def _settled_output(*, calls: int) -> ProcessorOutput:
    return ProcessorOutput(
        media_type="audio",
        markdown="# Settled audio\n",
        metadata={
            "provider": "google",
            "model": "test-audio-model",
            "transport": "google_files",
            "provider_call_count": calls,
            "current_run_provider_call_count": calls,
            "current_model_token_usage": (),
            "remote_file_deleted": True,
            "provider_client_closed": True,
        },
    )


def _partial_settled_output(*, calls: int) -> ProcessorOutput:
    return ProcessorOutput(
        media_type="audio",
        markdown="# Settled audio\n",
        status="partial",
        warnings=("The provider client could not be closed.",),
        metadata={
            "provider": "google",
            "model": "test-audio-model",
            "transport": "google_files",
            "provider_call_count": calls,
            "current_run_provider_call_count": calls,
            "current_model_token_usage": (),
            "remote_file_deleted": True,
            "provider_client_closed": False,
        },
    )


def test_video_interval_snapshot_cleanup_failure_keeps_state_and_exact_call_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processor = __import__(
        "ocrllm.processors.recognize_video_mp3",
        fromlist=["recognize_video_mp3"],
    )
    state_path = tmp_path / ".ocrllm-video-audio-resume.json"

    @contextmanager
    def failing_snapshot(*_args, **kwargs):
        assert kwargs["interval_mode"] is True
        yield _snapshot(tmp_path)
        raise OutputError(
            "The validated audio snapshot could not be removed after use.",
            code="OUTPUT_WRITE_FAILED",
        )

    def settle_intervals(*_args, **kwargs):
        assert kwargs["interval_minutes"] == 3
        kwargs["state_path"].write_text("paid-prefix", encoding="utf-8")
        return _settled_output(calls=2), 2

    monkeypatch.setattr(processor, "snapshot_video_mp3", failing_snapshot)
    monkeypatch.setattr(
        processor,
        "recognize_long_mp3_intervals",
        settle_intervals,
    )

    with pytest.raises(OutputError) as captured:
        recognize_video_mp3(
            tmp_path / "audio.mp3",
            config=_config(tmp_path),
            interval_minutes=3,
            state_path=state_path,
        )

    assert captured.value.details["provider_calls_attempted"] == 2
    assert state_path.read_text(encoding="utf-8") == "paid-prefix"


def test_video_long_audio_state_unlink_failure_returns_partial_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processor = __import__(
        "ocrllm.processors.recognize_video_mp3",
        fromlist=["recognize_video_mp3"],
    )
    state_path = tmp_path / ".ocrllm-video-audio-resume.json"

    @contextmanager
    def clean_snapshot(*_args, **_kwargs):
        yield _snapshot(tmp_path)

    def settle_whole(*_args, **kwargs):
        kwargs["state_path"].write_text("settled", encoding="utf-8")
        return _settled_output(calls=1), 1

    real_unlink = Path.unlink

    def fail_owned_state_unlink(path: Path, *args, **kwargs):
        if path == state_path:
            raise PermissionError("injected-state-unlink-failure")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(processor, "snapshot_video_mp3", clean_snapshot)
    monkeypatch.setattr(processor, "recognize_long_mp3_whole", settle_whole)
    monkeypatch.setattr(Path, "unlink", fail_owned_state_unlink)

    result = recognize_video_mp3(
        tmp_path / "audio.mp3",
        config=_config(tmp_path),
        interval_minutes=None,
        state_path=state_path,
    )

    assert result.status == "partial"
    assert result.metadata["resume_state_removed"] is False
    assert result.warnings == (
        "The temporary long-audio resume state could not be removed.",
    )
    assert state_path.read_text(encoding="utf-8") == "settled"


def test_video_whole_state_save_failure_reports_the_completed_provider_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processor = __import__(
        "ocrllm.processors.recognize_video_mp3",
        fromlist=["recognize_video_mp3"],
    )
    whole_processor = __import__(
        "ocrllm.processors.recognize_long_mp3_whole",
        fromlist=["recognize_long_mp3_whole"],
    )

    @contextmanager
    def clean_snapshot(*_args, **_kwargs):
        yield _snapshot(tmp_path)

    def recognize_once(*_args, **_kwargs):
        return SimpleNamespace(
            markdown="# Paid whole audio\n",
            input_tokens=101,
            output_tokens=17,
            remote_file_deleted=True,
            client_closed=True,
        )

    def fail_state_save(*_args, **_kwargs):
        raise OutputError(
            "The long-audio partial state could not be written atomically.",
            code="OUTPUT_WRITE_FAILED",
        )

    monkeypatch.setattr(processor, "snapshot_video_mp3", clean_snapshot)
    monkeypatch.setattr(whole_processor, "recognize_uploaded_mp3", recognize_once)
    monkeypatch.setattr(
        whole_processor,
        "save_long_audio_partial_state_atomically",
        fail_state_save,
    )

    with pytest.raises(OutputError) as captured:
        recognize_video_mp3(
            tmp_path / "audio.mp3",
            config=_config(tmp_path),
            interval_minutes=None,
            state_path=tmp_path / ".ocrllm-video-audio-resume.json",
        )

    assert captured.value.details["provider_calls_attempted"] == 1


def test_video_partial_long_audio_result_keeps_settled_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processor = __import__(
        "ocrllm.processors.recognize_video_mp3",
        fromlist=["recognize_video_mp3"],
    )
    state_path = tmp_path / ".ocrllm-video-audio-resume.json"

    @contextmanager
    def clean_snapshot(*_args, **_kwargs):
        yield _snapshot(tmp_path)

    def settle_intervals(*_args, **kwargs):
        kwargs["state_path"].write_text("settled", encoding="utf-8")
        return _partial_settled_output(calls=2), 2

    monkeypatch.setattr(processor, "snapshot_video_mp3", clean_snapshot)
    monkeypatch.setattr(
        processor,
        "recognize_long_mp3_intervals",
        settle_intervals,
    )

    result = recognize_video_mp3(
        tmp_path / "audio.mp3",
        config=_config(tmp_path),
        interval_minutes=3,
        state_path=state_path,
    )

    assert result.status == "partial"
    assert result.metadata["provider_client_closed"] is False
    assert state_path.read_text(encoding="utf-8") == "settled"
