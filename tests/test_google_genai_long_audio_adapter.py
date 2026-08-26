"""Contract tests for one native Google Files long-MP3 lifecycle."""

from __future__ import annotations

import importlib
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from ocrllm import (
    AudioModelSettings,
    Config,
    GoogleGenAISettings,
    recognize_long_mp3,
)
from ocrllm.errors import (
    Cancelled,
    ConfigError,
    InvalidSource,
    OutputError,
    ProviderError,
    ProviderUnavailable,
)


MODEL = "gemini-2.5-flash"
SOURCE = Path("owned-long-source.mp3")


class _HttpOptions:
    def __init__(self, *, timeout: int) -> None:
        self.timeout = timeout


class _Files:
    def __init__(
        self,
        events: list[str],
        *,
        initial_state: str = "ACTIVE",
        get_states: tuple[str, ...] = (),
        upload_error: Exception | None = None,
        delete_error: BaseException | None = None,
    ) -> None:
        self.events = events
        self.initial_state = initial_state
        self.get_states = list(get_states)
        self.upload_error = upload_error
        self.delete_error = delete_error
        self.upload_calls: list[Path] = []
        self.get_calls: list[str] = []
        self.delete_calls: list[str] = []

    def upload(self, *, file):
        self.events.append("upload")
        self.upload_calls.append(Path(file))
        if self.upload_error is not None:
            raise self.upload_error
        return _remote_file(self.initial_state)

    def get(self, *, name: str):
        self.events.append("get")
        self.get_calls.append(name)
        state = self.get_states.pop(0)
        return _remote_file(state)

    def delete(self, *, name: str):
        self.events.append("delete")
        self.delete_calls.append(name)
        if self.delete_error is not None:
            raise self.delete_error
        return SimpleNamespace()


class _Models:
    def __init__(
        self,
        events: list[str],
        *,
        served_models: tuple[str, ...] = (MODEL,),
        input_token_limit: object = None,
        generate_error: Exception | None = None,
    ) -> None:
        self.events = events
        self.served_models = served_models
        self.input_token_limit = input_token_limit
        self.generate_error = generate_error
        self.generate_calls: list[dict[str, object]] = []

    def list(self):
        self.events.append("catalog")
        return (
            SimpleNamespace(
                name=f"models/{model}",
                supported_actions=["generateContent"],
                input_token_limit=self.input_token_limit,
            )
            for model in self.served_models
        )

    def generate_content(self, *, model: str, contents):
        self.events.append("generate")
        self.generate_calls.append({"model": model, "contents": contents})
        if self.generate_error is not None:
            raise self.generate_error
        return SimpleNamespace(
            text="long transcript",
            candidates=(),
            prompt_feedback=None,
            usage_metadata=SimpleNamespace(
                prompt_token_count=101,
                candidates_token_count=17,
            ),
        )


class _Client:
    def __init__(
        self,
        files: _Files,
        models: _Models,
        events: list[str],
        *,
        close_error: Exception | None,
    ) -> None:
        self.files = files
        self.models = models
        self.events = events
        self.close_error = close_error
        self.closed = False

    def close(self) -> None:
        self.events.append("close")
        if self.close_error is not None:
            raise self.close_error
        self.closed = True


class _FakeGoogleModule:
    types = SimpleNamespace(HttpOptions=_HttpOptions)

    def __init__(
        self,
        *,
        initial_state: str = "ACTIVE",
        get_states: tuple[str, ...] = (),
        served_models: tuple[str, ...] = (MODEL,),
        input_token_limit: object = None,
        upload_error: Exception | None = None,
        generate_error: Exception | None = None,
        delete_error: BaseException | None = None,
        close_error: Exception | None = None,
    ) -> None:
        self.events: list[str] = []
        self.files = _Files(
            self.events,
            initial_state=initial_state,
            get_states=get_states,
            upload_error=upload_error,
            delete_error=delete_error,
        )
        self.models = _Models(
            self.events,
            served_models=served_models,
            input_token_limit=input_token_limit,
            generate_error=generate_error,
        )
        self.close_error = close_error
        self.clients: list[_Client] = []

    def Client(self, **_kwargs):
        client = _Client(
            self.files,
            self.models,
            self.events,
            close_error=self.close_error,
        )
        self.clients.append(client)
        return client


def _remote_file(state: str):
    return SimpleNamespace(
        name="files/owned-test-file",
        uri="https://provider.invalid/files/owned-test-file",
        mime_type="audio/mpeg",
        state=SimpleNamespace(name=state),
    )


def _config(**updates) -> Config:
    values = {
        "provider": GoogleGenAISettings(api_key="test-only-google-key"),
        "audio_model": AudioModelSettings(name=MODEL),
        "timeout_seconds": 10.0,
    }
    values.update(updates)
    return Config(**values)


def _install_fake_snapshot(monkeypatch, *, duration_seconds: float = 301.0) -> None:
    processor = importlib.import_module("ocrllm.processors.recognize_long_mp3")

    @contextmanager
    def fake_snapshot(_source, *, temp_dir):
        assert temp_dir is None
        yield SimpleNamespace(
            path=SOURCE,
            byte_size=12345,
            duration_seconds=duration_seconds,
        )

    monkeypatch.setattr(processor, "snapshot_long_mp3", fake_snapshot)


def _install_fake_sdk(monkeypatch, fake: _FakeGoogleModule) -> None:
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_uploaded_mp3"
    )
    monkeypatch.setattr(adapter, "load_google_genai", lambda: fake)


def test_public_long_mp3_runs_one_owned_files_lifecycle(monkeypatch) -> None:
    fake = _FakeGoogleModule(initial_state="PROCESSING", get_states=("ACTIVE",))
    _install_fake_snapshot(monkeypatch)
    _install_fake_sdk(monkeypatch, fake)
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_uploaded_mp3"
    )
    monkeypatch.setattr(adapter.time, "sleep", lambda _seconds: None)

    result = recognize_long_mp3(SOURCE, config=_config())

    assert result.source_type == "audio"
    assert result.markdown == "long transcript"
    assert result.output_path is None
    assert result.warnings == ()
    assert result.metadata["provider"] == "google"
    assert result.metadata["model"] == MODEL
    assert result.metadata["transport"] == "google_files"
    assert result.metadata["provider_call_count"] == 1
    assert result.metadata["remote_file_deleted"] is True
    assert result.metadata["duration_seconds"] == 301.0
    assert result.metadata["byte_size"] == 12345
    assert result.metadata["current_model_token_usage"] == (
        {"model": MODEL, "input_tokens": 101, "output_tokens": 17},
    )
    assert fake.events == ["catalog", "upload", "get", "generate", "delete", "close"]
    assert fake.files.upload_calls == [SOURCE]
    assert fake.files.get_calls == ["files/owned-test-file"]
    assert fake.files.delete_calls == ["files/owned-test-file"]
    assert len(fake.models.generate_calls) == 1
    contents = fake.models.generate_calls[0]["contents"]
    assert type(contents[0]) is str
    assert "NOSPEECH4OCRLLM" in contents[0]
    assert contents[1].name == "files/owned-test-file"
    assert fake.clients[0].closed is True


def test_files_workflow_waits_at_active_start_gate_before_sdk(monkeypatch) -> None:
    fake = _FakeGoogleModule()
    _install_fake_snapshot(monkeypatch)
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_uploaded_mp3"
    )
    starts: list[str] = []

    monkeypatch.setattr(
        adapter,
        "wait_for_provider_request_start",
        lambda cancellation: starts.append("gate"),
    )

    def load_after_gate():
        starts.append("sdk")
        return fake

    monkeypatch.setattr(adapter, "load_google_genai", load_after_gate)

    result = recognize_long_mp3(SOURCE, config=_config())

    assert result.status == "complete"
    assert starts == ["gate", "sdk"]


def test_missing_model_stops_before_upload(monkeypatch) -> None:
    fake = _FakeGoogleModule(served_models=("another-model",))
    _install_fake_snapshot(monkeypatch)
    _install_fake_sdk(monkeypatch, fake)

    with pytest.raises(ProviderUnavailable) as caught:
        recognize_long_mp3(SOURCE, config=_config())

    assert caught.value.details["provider_calls_attempted"] == 0
    assert fake.files.upload_calls == []
    assert fake.models.generate_calls == []
    assert fake.events == ["catalog", "close"]


def test_audio_that_fills_model_input_limit_stops_before_upload(monkeypatch) -> None:
    fake = _FakeGoogleModule(input_token_limit=9_633)
    _install_fake_snapshot(monkeypatch, duration_seconds=301.01)
    _install_fake_sdk(monkeypatch, fake)

    with pytest.raises(InvalidSource) as caught:
        recognize_long_mp3(SOURCE, config=_config())

    assert caught.value.code == "SOURCE_TOO_LARGE"
    assert caught.value.details["model"] == MODEL
    assert caught.value.details["provider_calls_attempted"] == 0
    assert caught.value.details["maximum_audio_only_duration_seconds"] == (
        9_632 / 32
    )
    assert fake.files.upload_calls == []
    assert fake.models.generate_calls == []
    assert fake.events == ["catalog", "close"]


def test_audio_below_advertised_model_input_limit_keeps_lifecycle(monkeypatch) -> None:
    fake = _FakeGoogleModule(input_token_limit=9_634)
    _install_fake_snapshot(monkeypatch, duration_seconds=301.01)
    _install_fake_sdk(monkeypatch, fake)

    result = recognize_long_mp3(SOURCE, config=_config())

    assert result.status == "complete"
    assert fake.events == ["catalog", "upload", "generate", "delete", "close"]


def test_missing_model_input_limit_preserves_one_request_lifecycle(monkeypatch) -> None:
    fake = _FakeGoogleModule(input_token_limit=None)
    _install_fake_snapshot(monkeypatch, duration_seconds=32_768.0)
    _install_fake_sdk(monkeypatch, fake)

    result = recognize_long_mp3(SOURCE, config=_config())

    assert result.status == "complete"
    assert fake.events == ["catalog", "upload", "generate", "delete", "close"]


@pytest.mark.parametrize("input_token_limit", (True, 0, -1, 1.0, "1048576"))
def test_invalid_model_input_limit_stops_before_upload(
    monkeypatch,
    input_token_limit,
) -> None:
    fake = _FakeGoogleModule(input_token_limit=input_token_limit)
    _install_fake_snapshot(monkeypatch)
    _install_fake_sdk(monkeypatch, fake)

    with pytest.raises(ProviderError) as caught:
        recognize_long_mp3(SOURCE, config=_config())

    assert caught.value.code == "PROVIDER_RESPONSE_INVALID"
    assert caught.value.details["provider"] == "google"
    assert caught.value.details["model"] == MODEL
    assert caught.value.details["failure_scope"] == "response"
    assert caught.value.details["provider_calls_attempted"] == 0
    assert fake.files.upload_calls == []
    assert fake.models.generate_calls == []
    assert fake.events == ["catalog", "close"]


def test_failed_remote_processing_is_deleted_without_generation(monkeypatch) -> None:
    fake = _FakeGoogleModule(initial_state="FAILED")
    _install_fake_snapshot(monkeypatch)
    _install_fake_sdk(monkeypatch, fake)

    with pytest.raises(ProviderError) as caught:
        recognize_long_mp3(SOURCE, config=_config())

    assert caught.value.code == "PROVIDER_RESPONSE_INVALID"
    assert caught.value.details["provider_calls_attempted"] == 0
    assert fake.models.generate_calls == []
    assert fake.events == ["catalog", "upload", "delete", "close"]


def test_upload_failure_has_no_remote_cleanup_or_generation(monkeypatch) -> None:
    fake = _FakeGoogleModule(
        upload_error=ConnectionError("PRIVATE UPLOAD BODY"),
    )
    _install_fake_snapshot(monkeypatch)
    _install_fake_sdk(monkeypatch, fake)

    with pytest.raises(ProviderError) as caught:
        recognize_long_mp3(SOURCE, config=_config())

    assert caught.value.code == "PROVIDER_NETWORK"
    assert caught.value.details["provider_calls_attempted"] == 0
    assert fake.files.delete_calls == []
    assert fake.models.generate_calls == []
    assert fake.events == ["catalog", "upload", "close"]


def test_generation_failure_preserves_primary_when_delete_also_fails(
    monkeypatch,
) -> None:
    fake = _FakeGoogleModule(
        generate_error=ConnectionError("PRIVATE GENERATION BODY"),
        delete_error=RuntimeError("PRIVATE DELETE URI"),
    )
    _install_fake_snapshot(monkeypatch)
    _install_fake_sdk(monkeypatch, fake)

    with pytest.raises(ProviderError) as caught:
        recognize_long_mp3(SOURCE, config=_config())

    assert caught.value.code == "PROVIDER_NETWORK"
    assert caught.value.details["provider_calls_attempted"] == 1
    assert caught.value.details["provider_file_cleanup_failed"] is True
    assert "PRIVATE" not in str(caught.value)
    assert fake.files.delete_calls == ["files/owned-test-file"]
    assert fake.clients[0].closed is True


def test_generation_failure_reports_successful_owned_cleanup(monkeypatch) -> None:
    fake = _FakeGoogleModule(
        generate_error=ProviderError(code="PROVIDER_RESPONSE_INVALID"),
    )
    _install_fake_snapshot(monkeypatch)
    _install_fake_sdk(monkeypatch, fake)

    with pytest.raises(ProviderError) as caught:
        recognize_long_mp3(SOURCE, config=_config())

    assert caught.value.details["provider_calls_attempted"] == 1
    assert caught.value.details["remote_file_deleted"] is True
    assert caught.value.details["provider_client_closed"] is True
    assert fake.events == ["catalog", "upload", "generate", "delete", "close"]


@pytest.mark.parametrize("signal_type", (KeyboardInterrupt, SystemExit))
def test_remote_delete_process_control_still_closes_client_and_snapshot(
    monkeypatch,
    signal_type,
) -> None:
    signal = signal_type("test-only cleanup stop")
    fake = _FakeGoogleModule(delete_error=signal)
    processor = importlib.import_module("ocrllm.processors.recognize_long_mp3")
    snapshot_events: list[str] = []

    @contextmanager
    def observed_snapshot(_source, *, temp_dir):
        assert temp_dir is None
        snapshot_events.append("enter")
        try:
            yield SimpleNamespace(
                path=SOURCE,
                byte_size=12345,
                duration_seconds=301.0,
            )
        finally:
            snapshot_events.append("cleanup")

    monkeypatch.setattr(processor, "snapshot_long_mp3", observed_snapshot)
    _install_fake_sdk(monkeypatch, fake)

    with pytest.raises(signal_type) as caught:
        recognize_long_mp3(SOURCE, config=_config())

    assert caught.value is signal
    assert fake.events == ["catalog", "upload", "generate", "delete", "close"]
    assert fake.files.delete_calls == ["files/owned-test-file"]
    assert len(fake.models.generate_calls) == 1
    assert fake.clients[0].closed is True
    assert snapshot_events == ["enter", "cleanup"]


def test_processing_timeout_deletes_upload_without_generation(monkeypatch) -> None:
    fake = _FakeGoogleModule(initial_state="PROCESSING")
    _install_fake_snapshot(monkeypatch)
    _install_fake_sdk(monkeypatch, fake)
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_uploaded_mp3"
    )
    moments = iter((10.0, 21.0))
    monkeypatch.setattr(adapter.time, "monotonic", lambda: next(moments))

    with pytest.raises(ProviderError) as caught:
        recognize_long_mp3(SOURCE, config=_config(timeout_seconds=10.0))

    assert caught.value.code == "PROVIDER_TIMEOUT"
    assert caught.value.details["provider_calls_attempted"] == 0
    assert fake.models.generate_calls == []
    assert fake.events == ["catalog", "upload", "delete", "close"]


def test_cancellation_during_processing_deletes_upload(monkeypatch) -> None:
    fake = _FakeGoogleModule(initial_state="PROCESSING")
    _install_fake_snapshot(monkeypatch)
    _install_fake_sdk(monkeypatch, fake)
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_uploaded_mp3"
    )
    cancellation = Event()

    def cancel_instead_of_sleep(_seconds: float) -> None:
        cancellation.set()

    monkeypatch.setattr(adapter.time, "sleep", cancel_instead_of_sleep)

    with pytest.raises(Cancelled) as caught:
        recognize_long_mp3(
            SOURCE,
            config=_config(cancellation=cancellation),
        )

    assert caught.value.details["provider_calls_attempted"] == 0
    assert fake.models.generate_calls == []
    assert fake.events == ["catalog", "upload", "delete", "close"]


def test_successful_transcript_discloses_remote_delete_failure(monkeypatch) -> None:
    fake = _FakeGoogleModule(delete_error=RuntimeError("PRIVATE DELETE URI"))
    _install_fake_snapshot(monkeypatch)
    _install_fake_sdk(monkeypatch, fake)

    result = recognize_long_mp3(SOURCE, config=_config())

    assert result.status == "partial"
    assert result.warnings == (
        "The Google Files upload could not be deleted after recognition.",
    )
    assert result.metadata["remote_file_deleted"] is False
    assert result.metadata["provider_call_count"] == 1
    assert fake.clients[0].closed is True


def test_successful_transcript_discloses_client_close_failure(monkeypatch) -> None:
    fake = _FakeGoogleModule(close_error=RuntimeError("PRIVATE CLOSE BODY"))
    _install_fake_snapshot(monkeypatch)
    _install_fake_sdk(monkeypatch, fake)

    result = recognize_long_mp3(SOURCE, config=_config())

    assert result.status == "partial"
    assert result.warnings == (
        "The Google GenAI client could not be closed after recognition.",
    )
    assert result.metadata["remote_file_deleted"] is True
    assert result.metadata["provider_client_closed"] is False


def test_completed_generation_is_counted_when_local_snapshot_cleanup_fails(
    monkeypatch,
) -> None:
    fake = _FakeGoogleModule()
    processor = importlib.import_module("ocrllm.processors.recognize_long_mp3")

    @contextmanager
    def cleanup_failing_snapshot(_source, *, temp_dir):
        yield SimpleNamespace(
            path=SOURCE,
            byte_size=12345,
            duration_seconds=301.0,
        )
        raise OutputError(
            "The validated audio snapshot could not be removed after use.",
            code="OUTPUT_WRITE_FAILED",
        )

    monkeypatch.setattr(processor, "snapshot_long_mp3", cleanup_failing_snapshot)
    _install_fake_sdk(monkeypatch, fake)

    with pytest.raises(OutputError) as caught:
        recognize_long_mp3(SOURCE, config=_config())

    assert caught.value.details["provider_calls_attempted"] == 1
    assert fake.files.delete_calls == ["files/owned-test-file"]
    assert fake.clients[0].closed is True


def test_pre_set_cancellation_stops_before_snapshot(monkeypatch) -> None:
    processor = importlib.import_module("ocrllm.processors.recognize_long_mp3")
    cancellation = Event()
    cancellation.set()
    snapshot_started = False

    def fail_snapshot(*_args, **_kwargs):
        nonlocal snapshot_started
        snapshot_started = True
        raise AssertionError("cancelled long audio must not be snapshotted")

    monkeypatch.setattr(processor, "snapshot_long_mp3", fail_snapshot)

    with pytest.raises(Cancelled):
        recognize_long_mp3(SOURCE, config=_config(cancellation=cancellation))

    assert snapshot_started is False


def test_long_mp3_rejects_overwrite_before_snapshot(monkeypatch, tmp_path) -> None:
    processor = importlib.import_module("ocrllm.processors.recognize_long_mp3")
    snapshot_started = False

    def fail_snapshot(*_args, **_kwargs):
        nonlocal snapshot_started
        snapshot_started = True
        raise AssertionError("invalid options must fail before snapshot")

    monkeypatch.setattr(processor, "snapshot_long_mp3", fail_snapshot)

    with pytest.raises(ConfigError):
        recognize_long_mp3(
            SOURCE,
            config=_config(output_dir=tmp_path, overwrite=True),
        )

    assert snapshot_started is False
