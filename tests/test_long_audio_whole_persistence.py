"""Public whole-file long-audio persistence and resume behavior."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from ocrllm import AudioModelSettings, Config, GoogleGenAISettings, recognize_long_mp3
from ocrllm.errors import (
    NoSpeechDetected,
    OutputError,
    OutputExists,
    ResumeStateError,
)


MODEL = "gemini-test-whole-audio"
SOURCE_SHA256 = "a" * 64


def _config(output_dir: Path, *, resume: bool = False, model: str = MODEL) -> Config:
    return Config(
        provider=GoogleGenAISettings(api_key="test-only-google-key"),
        audio_model=AudioModelSettings(name=model),
        output_dir=output_dir,
        resume=resume,
    )


def _install_fakes(
    monkeypatch,
    provider_calls: list[str],
    *,
    snapshot_cleanup_error: bool = False,
) -> tuple[object, object]:
    processor = __import__(
        "ocrllm.processors.recognize_long_mp3",
        fromlist=["recognize_long_mp3"],
    )
    whole_processor = __import__(
        "ocrllm.processors.recognize_long_mp3_whole",
        fromlist=["recognize_long_mp3_whole"],
    )

    @contextmanager
    def fake_snapshot(source: Path, *, temp_dir):
        assert temp_dir is None
        try:
            yield SimpleNamespace(
                path=source,
                byte_size=12_345,
                sha256=SOURCE_SHA256,
                duration_seconds=601.5,
            )
        finally:
            if snapshot_cleanup_error:
                raise OutputError(
                    "The validated audio snapshot could not be removed after use.",
                    code="OUTPUT_WRITE_FAILED",
                )

    def fake_provider(snapshot, *, prompt, config):
        provider_calls.append(config.audio_model.name)
        return SimpleNamespace(
            markdown="# Whole transcript\n\n$x^2+y^2$",
            input_tokens=101,
            output_tokens=17,
            remote_file_deleted=True,
            client_closed=True,
        )

    monkeypatch.setattr(processor, "snapshot_long_mp3", fake_snapshot)
    monkeypatch.setattr(whole_processor, "recognize_uploaded_mp3", fake_provider)
    return processor, whole_processor


def _root(output_dir: Path) -> Path:
    return output_dir / "lecture"


def _state_path(output_dir: Path) -> Path:
    return _root(output_dir) / ".ocrllm-long-audio-resume.json"


def test_new_whole_run_saves_before_atomic_publication_then_removes_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    provider_calls: list[str] = []
    processor, _whole_processor = _install_fakes(monkeypatch, provider_calls)
    events: list[str] = []
    output_module = __import__(
        "ocrllm.output.write_markdown_atomically",
        fromlist=["write_markdown_atomically"],
    )
    state_module = __import__(
        "ocrllm.audio.save_long_audio_partial_state_atomically",
        fromlist=["save_long_audio_partial_state_atomically"],
    )

    def observed_save(path, state):
        events.append("state")
        state_module.save_long_audio_partial_state_atomically(path, state)

    def observed_publish(path, markdown, *, overwrite):
        assert _state_path(output_dir).is_file()
        events.append("result")
        output_module.write_markdown_atomically(path, markdown, overwrite=overwrite)

    monkeypatch.setattr(
        processor,
        "save_long_audio_partial_state_atomically",
        observed_save,
    )
    monkeypatch.setattr(
        processor,
        "write_markdown_atomically",
        observed_publish,
        raising=False,
    )

    result = recognize_long_mp3(
        tmp_path / "lecture.mp3",
        config=_config(output_dir),
    )

    assert provider_calls == [MODEL]
    assert events == ["state", "result"]
    assert result.output_path == _root(output_dir) / "result.md"
    assert result.output_path.read_text(encoding="utf-8") == result.markdown
    assert not _state_path(output_dir).exists()
    assert result.metadata["current_run_provider_call_count"] == 1
    assert result.metadata["remote_file_deleted"] is True
    assert result.metadata["provider_client_closed"] is True


def test_whole_state_removal_failure_keeps_published_partial_result(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    provider_calls: list[str] = []
    _install_fakes(monkeypatch, provider_calls)
    state_path = _state_path(output_dir)
    real_unlink = Path.unlink

    def fail_state_unlink(path: Path, *args, **kwargs):
        if path == state_path:
            raise PermissionError("injected-state-unlink-failure")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_state_unlink)

    result = recognize_long_mp3(
        tmp_path / "lecture.mp3",
        config=_config(output_dir),
    )

    assert provider_calls == [MODEL]
    assert result.status == "partial"
    assert result.output_path == _root(output_dir) / "result.md"
    assert result.output_path.read_text(encoding="utf-8") == result.markdown
    assert state_path.is_file()
    assert result.metadata["resume_state_removed"] is False
    assert result.metadata["current_run_provider_call_count"] == 1
    assert result.metadata["remote_file_deleted"] is True
    assert result.metadata["provider_client_closed"] is True
    assert result.warnings == (
        "The temporary long-audio resume state could not be removed.",
    )


def test_failed_publication_preserves_paid_state_for_zero_call_resume(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    provider_calls: list[str] = []
    processor, _ = _install_fakes(monkeypatch, provider_calls)
    output_module = __import__(
        "ocrllm.output.write_markdown_atomically",
        fromlist=["write_markdown_atomically"],
    )

    def fail_publication(*_args, **_kwargs):
        raise OutputError(
            "The requested Markdown output could not be written atomically.",
            code="OUTPUT_WRITE_FAILED",
        )

    monkeypatch.setattr(
        processor,
        "write_markdown_atomically",
        fail_publication,
        raising=False,
    )
    with pytest.raises(OutputError) as first_error:
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(output_dir),
        )

    assert first_error.value.details["provider_calls_attempted"] == 1
    assert first_error.value.details["settled_model_usage"] == (
        {
            "model": MODEL,
            "input_count": 101,
            "output_count": 17,
            "unit": "tokens",
        },
    )
    assert first_error.value.details["remote_file_deleted"] is True
    assert first_error.value.details["provider_client_closed"] is True
    assert provider_calls == [MODEL]
    assert _state_path(output_dir).is_file()
    assert not (_root(output_dir) / "result.md").exists()

    monkeypatch.setattr(
        processor,
        "write_markdown_atomically",
        output_module.write_markdown_atomically,
        raising=False,
    )
    result = recognize_long_mp3(
        tmp_path / "lecture.mp3",
        config=_config(output_dir, resume=True),
    )

    assert provider_calls == [MODEL]
    assert result.markdown == "# Whole transcript\n\n$x^2+y^2$"
    assert result.metadata["current_run_provider_call_count"] == 0
    assert result.metadata["current_model_token_usage"] == ()
    assert result.metadata["historical_model_token_usage"] == (
        {"model": MODEL, "input_tokens": 101, "output_tokens": 17},
    )
    assert result.metadata["remote_file_deleted"] is True
    assert result.metadata["provider_client_closed"] is True
    assert result.output_path is not None and result.output_path.is_file()
    assert not _state_path(output_dir).exists()


def test_whole_no_speech_is_settled_and_replayed_without_provider_call(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    provider_calls: list[str] = []
    _processor, whole_processor = _install_fakes(monkeypatch, provider_calls)

    def no_speech_provider(_snapshot, *, prompt, config):
        provider_calls.append(config.audio_model.name)
        raise NoSpeechDetected(
            details={
                "provider": "google",
                "model": MODEL,
                "provider_calls_attempted": 1,
                "remote_file_deleted": True,
                "provider_client_closed": True,
            }
        )

    monkeypatch.setattr(
        whole_processor,
        "recognize_uploaded_mp3",
        no_speech_provider,
    )

    with pytest.raises(NoSpeechDetected) as first_error:
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(output_dir),
        )

    assert first_error.value.details["provider_calls_attempted"] == 1
    assert provider_calls == [MODEL]
    assert _state_path(output_dir).is_file()
    assert not (_root(output_dir) / "result.md").exists()

    with pytest.raises(NoSpeechDetected) as resumed_error:
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(output_dir, resume=True),
        )

    assert resumed_error.value.details["provider_calls_attempted"] == 0
    assert resumed_error.value.details["remote_file_deleted"] is True
    assert resumed_error.value.details["provider_client_closed"] is True
    assert provider_calls == [MODEL]
    assert _state_path(output_dir).is_file()
    assert not (_root(output_dir) / "result.md").exists()


def test_whole_state_save_failure_reports_the_completed_provider_call(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    provider_calls: list[str] = []
    processor, _whole_processor = _install_fakes(monkeypatch, provider_calls)

    def fail_state_save(*_args, **_kwargs):
        raise OutputError(
            "The long-audio partial state could not be written atomically.",
            code="OUTPUT_WRITE_FAILED",
        )

    monkeypatch.setattr(
        processor,
        "save_long_audio_partial_state_atomically",
        fail_state_save,
    )

    with pytest.raises(OutputError) as captured:
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(output_dir),
        )

    assert captured.value.details["provider_calls_attempted"] == 1
    assert provider_calls == [MODEL]
    assert not _root(output_dir).exists()


def test_resume_request_mismatch_stops_before_provider_dispatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    provider_calls: list[str] = []
    processor, _ = _install_fakes(monkeypatch, provider_calls)

    def fail_publication(*_args, **_kwargs):
        raise OutputError(code="OUTPUT_WRITE_FAILED")

    monkeypatch.setattr(
        processor,
        "write_markdown_atomically",
        fail_publication,
        raising=False,
    )
    with pytest.raises(OutputError):
        recognize_long_mp3(tmp_path / "lecture.mp3", config=_config(output_dir))

    with pytest.raises(ResumeStateError) as mismatch:
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(output_dir, resume=True, model="different-model"),
        )

    assert mismatch.value.code == "RESUME_STATE_MISMATCH"
    assert mismatch.value.details["provider_calls_attempted"] == 0
    assert provider_calls == [MODEL]


def test_new_run_collision_stops_before_snapshot_and_provider(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    _root(output_dir).mkdir(parents=True)
    provider_calls: list[str] = []
    processor, _ = _install_fakes(monkeypatch, provider_calls)
    snapshot_started = False

    def fail_snapshot(*_args, **_kwargs):
        nonlocal snapshot_started
        snapshot_started = True
        raise AssertionError("collision must stop before snapshot")

    monkeypatch.setattr(processor, "snapshot_long_mp3", fail_snapshot)

    with pytest.raises(OutputExists):
        recognize_long_mp3(tmp_path / "lecture.mp3", config=_config(output_dir))

    assert snapshot_started is False
    assert provider_calls == []


def test_paid_state_survives_snapshot_cleanup_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    provider_calls: list[str] = []
    _install_fakes(monkeypatch, provider_calls, snapshot_cleanup_error=True)

    with pytest.raises(OutputError) as captured:
        recognize_long_mp3(tmp_path / "lecture.mp3", config=_config(output_dir))

    assert captured.value.details["provider_calls_attempted"] == 1
    assert provider_calls == [MODEL]
    assert _state_path(output_dir).is_file()
    assert not (_root(output_dir) / "result.md").exists()
