"""Public serial interval recognition and paid-prefix resume behavior."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from ocrllm import AudioModelSettings, Config, GoogleGenAISettings, recognize_long_mp3
from ocrllm.audio.load_long_audio_partial_state import (
    load_long_audio_partial_state,
)
from ocrllm.errors import (
    Cancelled,
    ConfigError,
    NoSpeechDetected,
    OutputError,
    ProviderError,
    ResumeStateError,
)


MODEL = "gemini-test-interval-audio"


def _config(
    output_dir: Path,
    *,
    resume: bool = False,
    cancellation: object | None = None,
) -> Config:
    return Config(
        provider=GoogleGenAISettings(api_key="test-only-google-key"),
        audio_model=AudioModelSettings(name=MODEL),
        output_dir=output_dir,
        resume=resume,
        cancellation=cancellation,
    )


def _install_interval_fakes(monkeypatch, tmp_path: Path, responses: list[object]):
    processor = __import__(
        "ocrllm.processors.recognize_long_mp3",
        fromlist=["recognize_long_mp3"],
    )
    interval_processor = __import__(
        "ocrllm.processors.recognize_long_mp3_intervals",
        fromlist=["recognize_long_mp3_intervals"],
    )
    materialized: list[int] = []
    provider_calls: list[int] = []

    @contextmanager
    def fake_snapshot(_source: Path, *, temp_dir, interval_mode=False):
        assert interval_mode is True
        yield SimpleNamespace(
            path=tmp_path / "owned-source.mp3",
            byte_size=50_000,
            sha256="a" * 64,
            duration_seconds=601.0,
        )

    @contextmanager
    def fake_materialize(_source: Path, *, window):
        materialized.append(window.index)
        segment = tmp_path / f"segment-{window.index}.mp3"
        segment.write_bytes(b"interval")
        try:
            yield segment
        finally:
            segment.unlink(missing_ok=True)

    def fake_provider(snapshot, *, prompt, config):
        index = len(provider_calls)
        provider_calls.append(index)
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        assert "context only" in prompt
        return SimpleNamespace(
            markdown=response,
            input_tokens=100 + index,
            output_tokens=10 + index,
            remote_file_deleted=True,
            client_closed=True,
        )

    monkeypatch.setattr(processor, "snapshot_long_mp3", fake_snapshot)
    monkeypatch.setattr(
        interval_processor,
        "materialize_long_audio_interval",
        fake_materialize,
        raising=False,
    )
    monkeypatch.setattr(interval_processor, "recognize_uploaded_mp3", fake_provider)
    return interval_processor, materialized, provider_calls


@pytest.mark.parametrize("value", (True, 0, -1, 1.5, "5"))
def test_interval_minutes_rejects_non_positive_exact_integers_before_snapshot(
    tmp_path: Path,
    monkeypatch,
    value,
) -> None:
    processor = __import__(
        "ocrllm.processors.recognize_long_mp3",
        fromlist=["recognize_long_mp3"],
    )
    started = False

    def fail_snapshot(*_args, **_kwargs):
        nonlocal started
        started = True
        raise AssertionError("invalid interval must stop before snapshot")

    monkeypatch.setattr(processor, "snapshot_long_mp3", fail_snapshot)

    with pytest.raises(ConfigError):
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(tmp_path / "out"),
            interval_minutes=value,
        )

    assert started is False


def test_interval_mode_requires_persistent_output_before_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    processor = __import__(
        "ocrllm.processors.recognize_long_mp3",
        fromlist=["recognize_long_mp3"],
    )
    started = False

    def fail_snapshot(*_args, **_kwargs):
        nonlocal started
        started = True

    monkeypatch.setattr(processor, "snapshot_long_mp3", fail_snapshot)
    config = Config(
        provider=GoogleGenAISettings(api_key="test-only-google-key"),
        audio_model=AudioModelSettings(name=MODEL),
    )

    with pytest.raises(ConfigError):
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=config,
            interval_minutes=5,
        )

    assert started is False


def test_interval_run_saves_each_paid_prefix_then_publishes_ordered_markdown(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    _interval_processor, materialized, provider_calls = _install_interval_fakes(
        monkeypatch,
        tmp_path,
        ["first", "second", "third"],
    )
    persistence_owner = __import__(
        "ocrllm.processors.recognize_long_mp3",
        fromlist=["recognize_long_mp3"],
    )
    state_module = __import__(
        "ocrllm.audio.save_long_audio_partial_state_atomically",
        fromlist=["save_long_audio_partial_state_atomically"],
    )
    saved_prefixes: list[int] = []

    def observed_save(path, state):
        saved_prefixes.append(len(state.slots))
        state_module.save_long_audio_partial_state_atomically(path, state)

    monkeypatch.setattr(
        persistence_owner,
        "save_long_audio_partial_state_atomically",
        observed_save,
    )

    result = recognize_long_mp3(
        tmp_path / "lecture.mp3",
        config=_config(output_dir),
        interval_minutes=5,
    )

    assert materialized == [0, 1, 2]
    assert provider_calls == [0, 1, 2]
    assert saved_prefixes == [1, 2, 3]
    assert result.markdown == "first\n\nsecond\n\nthird"
    assert result.metadata["current_run_provider_call_count"] == 3
    assert result.output_path == output_dir / "lecture" / "result.md"
    assert not (output_dir / "lecture" / ".ocrllm-long-audio-resume.json").exists()


def test_interval_state_removal_failure_keeps_published_partial_result(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    _interval_processor, materialized, provider_calls = _install_interval_fakes(
        monkeypatch,
        tmp_path,
        ["first", "second", "third"],
    )
    state_path = output_dir / "lecture" / ".ocrllm-long-audio-resume.json"
    real_unlink = Path.unlink

    def fail_state_unlink(path: Path, *args, **kwargs):
        if path == state_path:
            raise PermissionError("injected-state-unlink-failure")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_state_unlink)

    result = recognize_long_mp3(
        tmp_path / "lecture.mp3",
        config=_config(output_dir),
        interval_minutes=5,
    )

    assert materialized == [0, 1, 2]
    assert provider_calls == [0, 1, 2]
    assert result.status == "partial"
    assert result.output_path == output_dir / "lecture" / "result.md"
    assert result.output_path.read_text(encoding="utf-8") == result.markdown
    assert state_path.is_file()
    assert result.metadata["resume_state_removed"] is False
    assert result.metadata["current_run_provider_call_count"] == 3
    assert result.metadata["remote_file_deleted"] is True
    assert result.metadata["provider_client_closed"] is True
    assert result.warnings == (
        "The temporary long-audio resume state could not be removed.",
    )


def test_interval_publication_failure_reports_saved_settlement(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    _interval_processor, materialized, provider_calls = _install_interval_fakes(
        monkeypatch,
        tmp_path,
        ["first", "second", "third"],
    )
    processor = __import__(
        "ocrllm.processors.recognize_long_mp3",
        fromlist=["recognize_long_mp3"],
    )
    write_markdown_atomically = processor.write_markdown_atomically

    def fail_publication(*_args, **_kwargs):
        raise OutputError(
            "The requested Markdown output could not be written atomically.",
            code="OUTPUT_WRITE_FAILED",
        )

    monkeypatch.setattr(
        processor,
        "write_markdown_atomically",
        fail_publication,
    )

    with pytest.raises(OutputError) as captured:
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(output_dir),
            interval_minutes=5,
        )

    assert captured.value.details["provider_calls_attempted"] == 3
    assert captured.value.details["settled_model_usage"] == (
        {
            "model": MODEL,
            "input_count": 303,
            "output_count": 33,
            "unit": "tokens",
        },
    )
    assert captured.value.details["remote_file_deleted"] is True
    assert captured.value.details["provider_client_closed"] is True
    assert materialized == [0, 1, 2]
    assert provider_calls == [0, 1, 2]
    assert (
        output_dir / "lecture" / ".ocrllm-long-audio-resume.json"
    ).is_file()
    assert not (output_dir / "lecture" / "result.md").exists()

    monkeypatch.setattr(
        processor,
        "write_markdown_atomically",
        write_markdown_atomically,
    )
    resumed = recognize_long_mp3(
        tmp_path / "lecture.mp3",
        config=_config(output_dir, resume=True),
    )

    assert resumed.markdown == "first\n\nsecond\n\nthird"
    assert resumed.metadata["current_run_provider_call_count"] == 0
    assert materialized == [0, 1, 2]
    assert provider_calls == [0, 1, 2]
    assert not (
        output_dir / "lecture" / ".ocrllm-long-audio-resume.json"
    ).exists()


def test_interval_failure_preserves_prefix_and_resume_uses_saved_parameters(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    processor, materialized, provider_calls = _install_interval_fakes(
        monkeypatch,
        tmp_path,
        ["unused-first", "unused-second"],
    )

    def first_then_fail(snapshot, *, prompt, config):
        index = len(provider_calls)
        provider_calls.append(index)
        if index == 0:
            return SimpleNamespace(
                markdown="first",
                input_tokens=100,
                output_tokens=10,
                remote_file_deleted=False,
                client_closed=True,
            )
        raise ProviderError(
            code="PROVIDER_UNAVAILABLE",
            details={
                "provider_calls_attempted": 1,
                "remote_file_deleted": True,
                "provider_client_closed": True,
            },
        )

    monkeypatch.setattr(processor, "recognize_uploaded_mp3", first_then_fail)

    with pytest.raises(ProviderError) as first_failure:
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(output_dir),
            interval_minutes=5,
        )

    assert first_failure.value.details["provider_calls_attempted"] == 2
    assert first_failure.value.details["persisted_interval_count"] == 1
    assert first_failure.value.details["settled_model_usage"] == (
        {
            "model": MODEL,
            "input_count": 100,
            "output_count": 10,
            "unit": "tokens",
        },
    )
    assert first_failure.value.details["remote_file_deleted"] is False
    assert first_failure.value.details["provider_client_closed"] is True
    assert materialized == [0, 1]
    assert provider_calls == [0, 1]
    state_path = output_dir / "lecture" / ".ocrllm-long-audio-resume.json"
    assert state_path.is_file()

    _processor, resumed_materialized, resumed_calls = _install_interval_fakes(
        monkeypatch,
        tmp_path,
        ["second", "third"],
    )
    result = recognize_long_mp3(
        tmp_path / "lecture.mp3",
        config=_config(output_dir, resume=True),
    )

    assert resumed_materialized == [1, 2]
    assert resumed_calls == [0, 1]
    assert result.markdown == "first\n\nsecond\n\nthird"
    assert result.metadata["current_run_provider_call_count"] == 2
    assert not state_path.exists()


def test_resume_rejects_changed_interval_before_materialization_or_provider(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    _install_interval_fakes(
        monkeypatch,
        tmp_path,
        ["first", ProviderError(code="PROVIDER_UNAVAILABLE")],
    )
    with pytest.raises(ProviderError):
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(output_dir),
            interval_minutes=5,
        )

    processor, materialized, calls = _install_interval_fakes(
        monkeypatch,
        tmp_path,
        ["must not run"],
    )
    with pytest.raises(ResumeStateError) as captured:
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(output_dir, resume=True),
            interval_minutes=4,
        )

    assert captured.value.code == "RESUME_STATE_MISMATCH"
    assert materialized == []
    assert calls == []


def _no_speech(
    *,
    remote_file_deleted: bool = True,
    provider_client_closed: bool = True,
) -> NoSpeechDetected:
    return NoSpeechDetected(
        details={
            "provider": "google",
            "model": MODEL,
            "provider_calls_attempted": 1,
            "remote_file_deleted": remote_file_deleted,
            "provider_client_closed": provider_client_closed,
        }
    )


def test_no_speech_interval_is_settled_and_not_recalled_on_resume(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    _install_interval_fakes(
        monkeypatch,
        tmp_path,
        [
            "first",
            _no_speech(),
            ProviderError(
                code="PROVIDER_UNAVAILABLE",
                details={"provider_calls_attempted": 1},
            ),
        ],
    )
    with pytest.raises(ProviderError) as first_error:
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(output_dir),
            interval_minutes=5,
        )
    assert first_error.value.details["provider_calls_attempted"] == 3

    _processor, materialized, calls = _install_interval_fakes(
        monkeypatch,
        tmp_path,
        ["third"],
    )
    result = recognize_long_mp3(
        tmp_path / "lecture.mp3",
        config=_config(output_dir, resume=True),
    )

    assert materialized == [2]
    assert calls == [0]
    assert result.markdown == "first\n\nthird"
    assert result.metadata["provider_call_count"] == 3
    assert result.metadata["current_run_provider_call_count"] == 1


def test_all_no_speech_resume_replays_typed_result_without_provider_calls(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    _install_interval_fakes(
        monkeypatch,
        tmp_path,
        [
            _no_speech(remote_file_deleted=False),
            _no_speech(provider_client_closed=False),
            _no_speech(),
        ],
    )
    with pytest.raises(NoSpeechDetected) as first_error:
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(output_dir),
            interval_minutes=5,
        )
    assert first_error.value.details["provider_calls_attempted"] == 3
    assert first_error.value.details["remote_file_deleted"] is False
    assert first_error.value.details["provider_client_closed"] is False

    _processor, materialized, calls = _install_interval_fakes(
        monkeypatch,
        tmp_path,
        [],
    )
    with pytest.raises(NoSpeechDetected) as resumed_error:
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(output_dir, resume=True),
        )

    assert resumed_error.value.details["provider_calls_attempted"] == 0
    assert resumed_error.value.details["remote_file_deleted"] is False
    assert resumed_error.value.details["provider_client_closed"] is False
    assert materialized == []
    assert calls == []


def test_paid_interval_is_saved_before_materializer_cleanup_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    processor, _materialized, calls = _install_interval_fakes(
        monkeypatch,
        tmp_path,
        ["paid first"],
    )

    @contextmanager
    def cleanup_fails(_source: Path, *, window):
        segment = tmp_path / f"cleanup-fails-{window.index}.mp3"
        segment.write_bytes(b"interval")
        yield segment
        raise OutputError(code="OUTPUT_WRITE_FAILED")

    monkeypatch.setattr(processor, "materialize_long_audio_interval", cleanup_fails)
    with pytest.raises(OutputError) as captured:
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(output_dir),
            interval_minutes=5,
        )

    assert captured.value.details["provider_calls_attempted"] == 1
    assert captured.value.details["persisted_interval_count"] == 1
    assert captured.value.details["settled_model_usage"] == (
        {
            "model": MODEL,
            "input_count": 100,
            "output_count": 10,
            "unit": "tokens",
        },
    )
    assert captured.value.details["remote_file_deleted"] is True
    assert captured.value.details["provider_client_closed"] is True
    assert calls == [0]
    assert (output_dir / "lecture" / ".ocrllm-long-audio-resume.json").is_file()


def test_cancellation_after_saved_interval_reports_current_settlement(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    cancellation = Event()
    _interval_processor, materialized, provider_calls = _install_interval_fakes(
        monkeypatch,
        tmp_path,
        ["first", "must not run"],
    )
    processor = __import__(
        "ocrllm.processors.recognize_long_mp3",
        fromlist=["recognize_long_mp3"],
    )
    state_module = __import__(
        "ocrllm.audio.save_long_audio_partial_state_atomically",
        fromlist=["save_long_audio_partial_state_atomically"],
    )

    def save_then_cancel(path, state):
        state_module.save_long_audio_partial_state_atomically(path, state)
        cancellation.set()

    monkeypatch.setattr(
        processor,
        "save_long_audio_partial_state_atomically",
        save_then_cancel,
    )

    with pytest.raises(Cancelled) as captured:
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(output_dir, cancellation=cancellation),
            interval_minutes=5,
        )

    assert materialized == [0]
    assert provider_calls == [0]
    assert captured.value.details["provider_calls_attempted"] == 1
    assert captured.value.details["persisted_interval_count"] == 1
    assert captured.value.details["settled_model_usage"] == (
        {
            "model": MODEL,
            "input_count": 100,
            "output_count": 10,
            "unit": "tokens",
        },
    )
    assert captured.value.details["remote_file_deleted"] is True
    assert captured.value.details["provider_client_closed"] is True


def test_interval_state_save_failure_preserves_usage_and_cleanup_facts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    _interval_processor, materialized, provider_calls = _install_interval_fakes(
        monkeypatch,
        tmp_path,
        ["first", "second", "third"],
    )
    processor = __import__(
        "ocrllm.processors.recognize_long_mp3",
        fromlist=["recognize_long_mp3"],
    )

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
            interval_minutes=5,
        )

    assert materialized == [0]
    assert provider_calls == [0]
    assert captured.value.details["provider_calls_attempted"] == 1
    assert captured.value.details["persisted_interval_count"] == 0
    assert captured.value.details["settled_model_usage"] == (
        {
            "model": MODEL,
            "input_count": 100,
            "output_count": 10,
            "unit": "tokens",
        },
    )
    assert captured.value.details["remote_file_deleted"] is True
    assert captured.value.details["provider_client_closed"] is True
    assert not (output_dir / "lecture").exists()


def test_later_interval_state_save_failure_reports_all_current_settlement(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    interval_processor, materialized, provider_calls = _install_interval_fakes(
        monkeypatch,
        tmp_path,
        ["unused-first", "unused-second", "unused-third"],
    )
    processor = __import__(
        "ocrllm.processors.recognize_long_mp3",
        fromlist=["recognize_long_mp3"],
    )
    state_module = __import__(
        "ocrllm.audio.save_long_audio_partial_state_atomically",
        fromlist=["save_long_audio_partial_state_atomically"],
    )
    save_calls: list[int] = []

    def provider(snapshot, *, prompt, config):
        index = len(provider_calls)
        provider_calls.append(index)
        return SimpleNamespace(
            markdown=("first", "second")[index],
            input_tokens=100 + index,
            output_tokens=10 + index,
            remote_file_deleted=index != 0,
            client_closed=True,
        )

    def fail_second_save(path, state):
        save_calls.append(len(state.slots))
        if len(state.slots) == 2:
            raise OutputError(
                "The long-audio partial state could not be written atomically.",
                code="OUTPUT_WRITE_FAILED",
            )
        state_module.save_long_audio_partial_state_atomically(path, state)

    monkeypatch.setattr(interval_processor, "recognize_uploaded_mp3", provider)
    monkeypatch.setattr(
        processor,
        "save_long_audio_partial_state_atomically",
        fail_second_save,
    )

    with pytest.raises(OutputError) as captured:
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(output_dir),
            interval_minutes=5,
        )

    assert materialized == [0, 1]
    assert provider_calls == [0, 1]
    assert save_calls == [1, 2]
    assert captured.value.details["provider_calls_attempted"] == 2
    assert captured.value.details["persisted_interval_count"] == 1
    assert captured.value.details["settled_model_usage"] == (
        {
            "model": MODEL,
            "input_count": 201,
            "output_count": 21,
            "unit": "tokens",
        },
    )
    assert captured.value.details["remote_file_deleted"] is False
    assert captured.value.details["provider_client_closed"] is True
    state_path = output_dir / "lecture" / ".ocrllm-long-audio-resume.json"
    saved = load_long_audio_partial_state(state_path)
    assert saved is not None
    assert len(saved.slots) == 1
    assert saved.slots[0].provider_file_cleanup_succeeded is False
