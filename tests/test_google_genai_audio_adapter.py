"""Failing-first contract for native Google short-MP3 recognition."""

from __future__ import annotations

import importlib
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

import ocrllm
from ocrllm import (
    AudioModelSettings,
    Config,
    GoogleGenAISettings,
    recognize,
    recognize_batch,
)
from ocrllm.errors import (
    Cancelled,
    ConfigError,
    InvalidSource,
    NoSpeechDetected,
    OutputError,
    ProviderError,
    ProviderUnavailable,
)


MODEL = "gemini-2.5-flash"
FIXTURE = Path(__file__).parent / "fixtures" / "audio" / "a1" / "mp3" / "valid_cbr.mp3"
CORRUPT_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "audio"
    / "a1"
    / "mp3"
    / "corrupted_middle.mp3"
)


class _Part:
    @staticmethod
    def from_bytes(*, data: bytes, mime_type: str):
        return {"data": data, "mime_type": mime_type}


class _HttpOptions:
    def __init__(self, *, timeout: int) -> None:
        self.timeout = timeout


class _Models:
    def __init__(self, *, text: str = "synthetic speech", error: Exception | None = None):
        self.text = text
        self.error = error
        self.list_calls = 0
        self.generate_calls: list[dict[str, object]] = []

    def list(self):
        self.list_calls += 1
        return (
            SimpleNamespace(
                name=f"models/{MODEL}", supported_actions=["generateContent"]
            ),
        )

    def generate_content(self, *, model: str, contents):
        self.generate_calls.append({"model": model, "contents": contents})
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            text=self.text,
            candidates=(),
            prompt_feedback=None,
            usage_metadata=SimpleNamespace(
                prompt_token_count=17,
                candidates_token_count=5,
            ),
        )


class _Client:
    def __init__(self, models: _Models, *, close_error: Exception | None) -> None:
        self.models = models
        self.close_error = close_error
        self.closed = False

    def close(self) -> None:
        if self.close_error is not None:
            raise self.close_error
        self.closed = True


class _FakeGoogleModule:
    types = SimpleNamespace(Part=_Part, HttpOptions=_HttpOptions)

    def __init__(
        self,
        *,
        text: str = "synthetic speech",
        error: Exception | None = None,
        close_error: Exception | None = None,
    ):
        self.models = _Models(text=text, error=error)
        self.close_error = close_error
        self.clients: list[_Client] = []

    def Client(self, **_kwargs):
        client = _Client(self.models, close_error=self.close_error)
        self.clients.append(client)
        return client


def _config(**updates) -> Config:
    values = {
        "provider": GoogleGenAISettings(api_key="test-only-google-key"),
        "audio_model": AudioModelSettings(name=MODEL),
    }
    values.update(updates)
    return Config(**values)


def test_audio_model_settings_is_public_exact_frozen_and_copied() -> None:
    settings = AudioModelSettings(name=MODEL)

    assert type(settings) is AudioModelSettings
    assert Config(audio_model=settings).audio_model == settings
    with pytest.raises(Exception):
        settings.name = "changed"

    class SettingsSubclass(AudioModelSettings):
        pass

    with pytest.raises(ConfigError, match="exact AudioModelSettings"):
        Config(audio_model=SettingsSubclass(name=MODEL))


@pytest.mark.parametrize("name", ["", " model", "model ", "bad\nmodel", "bad\x7fmodel"])
def test_audio_model_settings_rejects_inexact_model_names(name) -> None:
    with pytest.raises(ConfigError):
        AudioModelSettings(name=name)


def test_google_audio_request_is_prompt_first_inline_mp3_and_bounded() -> None:
    builder = importlib.import_module(
        "ocrllm.providers.google_genai.build_google_genai_audio_request"
    )
    request = builder.build_google_genai_audio_request(
        FIXTURE,
        prompt="transcribe",
        model=MODEL,
    )

    assert request.model == MODEL
    assert request.contents[0] == "transcribe"
    assert request.contents[1].mime_type == "audio/mpeg"
    assert request.contents[1].data == FIXTURE.read_bytes()
    assert request.inline_byte_count == FIXTURE.stat().st_size
    assert request.wire_byte_upper_bound >= request.inline_byte_count
    assert request.wire_byte_upper_bound < builder.MAX_GOOGLE_AUDIO_WIRE_BYTES


def test_google_audio_oversize_fails_before_sdk_load(monkeypatch) -> None:
    builder = importlib.import_module(
        "ocrllm.providers.google_genai.build_google_genai_audio_request"
    )
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_short_mp3"
    )
    monkeypatch.setattr(builder, "MAX_GOOGLE_AUDIO_WIRE_BYTES", 1)
    loaded = False

    def fail_load():
        nonlocal loaded
        loaded = True
        raise AssertionError("SDK must not load before bounded preflight")

    monkeypatch.setattr(adapter, "load_google_genai", fail_load)
    with pytest.raises(InvalidSource) as caught:
        recognize(FIXTURE, config=_config())

    assert caught.value.code == "SOURCE_TOO_LARGE"
    assert loaded is False


def test_invalid_mp3_fails_before_sdk_load(monkeypatch) -> None:
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_short_mp3"
    )
    loaded = False

    def fail_load():
        nonlocal loaded
        loaded = True
        raise AssertionError("SDK must not load before MP3 validation")

    monkeypatch.setattr(adapter, "load_google_genai", fail_load)
    with pytest.raises(InvalidSource) as caught:
        recognize(CORRUPT_FIXTURE, config=_config())

    assert caught.value.code == "SOURCE_INVALID"
    assert loaded is False


def test_pre_set_google_audio_cancellation_stops_before_snapshot(monkeypatch) -> None:
    processor = importlib.import_module("ocrllm.processors.recognize_short_mp3")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    cancellation = Event()
    cancellation.set()
    snapshot_started = False

    def fail_snapshot(*_args, **_kwargs):
        nonlocal snapshot_started
        snapshot_started = True
        raise AssertionError("cancelled audio must not be snapshotted")

    monkeypatch.setattr(processor, "snapshot_short_mp3", fail_snapshot)

    with pytest.raises(Cancelled) as caught:
        recognize(
            FIXTURE,
            config=Config(
                provider=GoogleGenAISettings(),
                audio_model=AudioModelSettings(name=MODEL),
                cancellation=cancellation,
            ),
        )

    assert caught.value.code == "CANCELLED"
    assert snapshot_started is False


def test_missing_google_audio_credential_stops_before_snapshot(monkeypatch) -> None:
    processor = importlib.import_module("ocrllm.processors.recognize_short_mp3")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    snapshot_started = False

    def fail_snapshot(*_args, **_kwargs):
        nonlocal snapshot_started
        snapshot_started = True
        raise AssertionError("missing credential must stop before audio snapshot")

    monkeypatch.setattr(processor, "snapshot_short_mp3", fail_snapshot)
    config = Config(
        provider=GoogleGenAISettings(),
        audio_model=AudioModelSettings(name=MODEL),
    )

    with pytest.raises(ConfigError) as caught:
        recognize(FIXTURE, config=config)

    assert caught.value.code == "CONFIG_MISSING"
    assert caught.value.details["provider_calls_attempted"] == 0
    assert snapshot_started is False


def test_batch_missing_google_audio_credential_stops_before_decode(monkeypatch) -> None:
    preflight = importlib.import_module("ocrllm.preflight_recognition_batch")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    decode_started = False

    def fail_decode(*_args, **_kwargs):
        nonlocal decode_started
        decode_started = True
        raise AssertionError("missing credential must stop before batch audio decode")

    monkeypatch.setattr(preflight, "probe_short_mp3", fail_decode)
    config = Config(
        provider=GoogleGenAISettings(),
        audio_model=AudioModelSettings(name=MODEL),
    )

    with pytest.raises(ConfigError) as caught:
        recognize_batch((FIXTURE,), config=config)

    assert caught.value.code == "CONFIG_MISSING"
    assert caught.value.details["provider_calls_attempted"] == 0
    assert decode_started is False


def test_google_audio_adapter_checks_catalog_before_generate(monkeypatch) -> None:
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_short_mp3"
    )
    fake = _FakeGoogleModule()
    fake.models.list = lambda: (
        SimpleNamespace(name="models/another-model", supported_actions=["generateContent"]),
    )
    monkeypatch.setattr(adapter, "load_google_genai", lambda: fake)

    with pytest.raises(ProviderUnavailable) as caught:
        recognize(FIXTURE, config=_config())

    assert caught.value.details["failure_scope"] == "model"
    assert caught.value.details["provider_calls_attempted"] == 0
    assert fake.models.generate_calls == []
    assert fake.clients[0].closed is True


def test_google_audio_sdk_content_failure_is_not_counted_as_dispatch(monkeypatch) -> None:
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_short_mp3"
    )
    fake = _FakeGoogleModule()

    def fail_from_bytes(**_kwargs):
        raise ValueError("PRIVATE SDK CONTENT ERROR")

    fake.types = SimpleNamespace(
        Part=SimpleNamespace(from_bytes=fail_from_bytes),
        HttpOptions=_HttpOptions,
    )
    monkeypatch.setattr(adapter, "load_google_genai", lambda: fake)

    with pytest.raises(ProviderError) as caught:
        recognize(FIXTURE, config=_config())

    assert caught.value.details["provider_calls_attempted"] == 0
    assert "PRIVATE SDK CONTENT ERROR" not in str(caught.value)
    assert fake.models.generate_calls == []
    assert fake.clients[0].closed is True


def test_public_google_audio_result_usage_order_and_snapshot_cleanup(
    tmp_path, monkeypatch
) -> None:
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_short_mp3"
    )
    fake = _FakeGoogleModule()
    monkeypatch.setattr(adapter, "load_google_genai", lambda: fake)
    temp_dir = tmp_path / "snapshots"

    result = recognize(FIXTURE, config=_config(temp_dir=temp_dir))

    assert result.source_type == "audio"
    assert result.markdown == "synthetic speech"
    assert result.output_path is None
    assert result.metadata["provider"] == "google"
    assert result.metadata["model"] == MODEL
    assert result.metadata["provider_call_count"] == 1
    assert result.metadata["current_model_token_usage"] == (
        {"model": MODEL, "input_tokens": 17, "output_tokens": 5},
    )
    assert result.metadata["duration_seconds"] == 0.5
    assert result.metadata["byte_size"] == FIXTURE.stat().st_size
    call = fake.models.generate_calls[0]
    assert call["model"] == MODEL
    assert type(call["contents"][0]) is str
    assert "NOSPEECH4OCRLLM" in call["contents"][0]
    assert call["contents"][1]["mime_type"] == "audio/mpeg"
    assert fake.clients[0].closed is True
    assert list(temp_dir.glob("ocrllm-audio-*")) == []


def test_short_audio_preserves_result_when_cancelled_during_synchronous_call(
    tmp_path,
    monkeypatch,
) -> None:
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_short_mp3"
    )
    cancellation = Event()
    fake = _FakeGoogleModule()
    generate_content = fake.models.generate_content

    def set_cancellation_then_return_response(*, model, contents):
        cancellation.set()
        return generate_content(model=model, contents=contents)

    monkeypatch.setattr(
        fake.models,
        "generate_content",
        set_cancellation_then_return_response,
    )
    monkeypatch.setattr(adapter, "load_google_genai", lambda: fake)
    temp_dir = tmp_path / "snapshots"

    result = recognize(
        FIXTURE,
        config=_config(cancellation=cancellation, temp_dir=temp_dir),
    )

    assert cancellation.is_set()
    assert result.status == "complete"
    assert result.markdown == "synthetic speech"
    assert result.output_path is None
    assert fake.models.list_calls == 1
    assert len(fake.models.generate_calls) == 1
    assert result.metadata["provider_call_count"] == 1
    assert result.metadata["current_model_token_usage"] == (
        {"model": MODEL, "input_tokens": 17, "output_tokens": 5},
    )
    assert fake.clients[0].closed is True
    assert list(temp_dir.glob("ocrllm-audio-*")) == []


def test_successful_short_audio_discloses_client_close_failure(
    tmp_path,
    monkeypatch,
) -> None:
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_short_mp3"
    )
    fake = _FakeGoogleModule(close_error=RuntimeError("PRIVATE CLOSE BODY"))
    monkeypatch.setattr(adapter, "load_google_genai", lambda: fake)

    result = recognize(FIXTURE, config=_config(temp_dir=tmp_path / "snapshots"))

    assert result.status == "partial"
    assert result.markdown == "synthetic speech"
    assert result.warnings == (
        "The Google GenAI client could not be closed after recognition.",
    )
    assert result.metadata["provider_call_count"] == 1
    assert result.metadata["provider_client_closed"] is False
    assert result.metadata["current_model_token_usage"] == (
        {"model": MODEL, "input_tokens": 17, "output_tokens": 5},
    )
    assert list((tmp_path / "snapshots").glob("ocrllm-audio-*")) == []


def test_google_audio_reports_completed_call_when_snapshot_cleanup_fails(
    tmp_path, monkeypatch
) -> None:
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_short_mp3"
    )
    processor = importlib.import_module("ocrllm.processors.recognize_short_mp3")
    fake = _FakeGoogleModule()
    monkeypatch.setattr(adapter, "load_google_genai", lambda: fake)
    source_bytes = FIXTURE.read_bytes()
    temp_dir = tmp_path / "snapshots"
    cleanup_error = OutputError(
        "The validated audio snapshot could not be removed after use.",
        code="OUTPUT_WRITE_FAILED",
    )

    @contextmanager
    def cleanup_failing_snapshot(_source, *, temp_dir):
        yield SimpleNamespace(
            path=FIXTURE,
            byte_size=FIXTURE.stat().st_size,
            duration_seconds=0.5,
        )
        raise cleanup_error

    monkeypatch.setattr(processor, "snapshot_short_mp3", cleanup_failing_snapshot)

    with pytest.raises(OutputError) as caught:
        recognize(FIXTURE, config=_config(temp_dir=temp_dir))

    assert caught.value is cleanup_error
    assert caught.value.code == "OUTPUT_WRITE_FAILED"
    assert caught.value.retryable is False
    assert caught.value.details["provider_calls_attempted"] == 1
    assert caught.value.details["settled_model_usage"] == (
        {
            "model": MODEL,
            "input_count": 17,
            "output_count": 5,
            "unit": "tokens",
        },
    )
    assert caught.value.details["provider_client_closed"] is True
    assert len(fake.models.generate_calls) == 1
    assert fake.clients[0].closed is True
    assert FIXTURE.read_bytes() == source_bytes


def test_serial_audio_batch_preserves_item_call_counts_and_order(
    tmp_path, monkeypatch
) -> None:
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_short_mp3"
    )
    fake = _FakeGoogleModule()
    successful_generate = fake.models.generate_content

    def succeed_then_fail(*, model, contents):
        if fake.models.generate_calls:
            fake.models.generate_calls.append({"model": model, "contents": contents})
            raise ConnectionError("PRIVATE SECOND AUDIO FAILURE")
        return successful_generate(model=model, contents=contents)

    fake.models.generate_content = succeed_then_fail
    monkeypatch.setattr(adapter, "load_google_genai", lambda: fake)
    temp_dir = tmp_path / "snapshots"

    outcomes = recognize_batch(
        (FIXTURE, FIXTURE, FIXTURE),
        config=_config(temp_dir=temp_dir),
    )

    assert [outcome.index for outcome in outcomes] == [0, 1, 2]
    assert outcomes[0].result is not None
    assert outcomes[0].result.metadata["provider_call_count"] == 1
    assert outcomes[1].error is not None
    assert outcomes[1].error.code == "PROVIDER_NETWORK"
    assert outcomes[1].error.details["provider_calls_attempted"] == 1
    assert "PRIVATE SECOND AUDIO FAILURE" not in str(outcomes[1].error)
    assert type(outcomes[2].error) is Cancelled
    assert "provider_calls_attempted" not in outcomes[2].error.details
    assert len(fake.models.generate_calls) == 2
    assert len(fake.clients) == 2
    assert all(client.closed for client in fake.clients)
    assert list(temp_dir.glob("ocrllm-audio-*")) == []


def test_google_audio_response_keeps_missing_usage_unknown() -> None:
    parser = importlib.import_module(
        "ocrllm.providers.google_genai.parse_google_genai_audio_response"
    )
    parsed = parser.parse_google_genai_audio_response(
        SimpleNamespace(
            text="transcript",
            candidates=(),
            prompt_feedback=None,
            usage_metadata=None,
        ),
        model=MODEL,
    )

    assert parsed.input_tokens is None
    assert parsed.output_tokens is None
    assert parsed.client_closed is True


@pytest.mark.parametrize(
    ("text", "expected_code", "expected_reason"),
    (
        (
            "transcript NOSPEECH4OCRLLM",
            "PROVIDER_RESPONSE_INVALID",
            "invalid_no_speech_marker",
        ),
        (" \n<!-- hidden -->\n", "PROVIDER_RESPONSE_INVALID", "empty"),
        (
            "I'm sorry, I cannot transcribe this.",
            "PROVIDER_REFUSED_RECOGNITION",
            "refusal",
        ),
        ("# Transcript\n\ud800\n", "PROVIDER_RESPONSE_INVALID", "invalid_encoding"),
    ),
)
def test_google_audio_post_parse_rejection_preserves_settled_usage(
    text,
    expected_code,
    expected_reason,
) -> None:
    parser = importlib.import_module(
        "ocrllm.providers.google_genai.parse_google_genai_audio_response"
    )
    response = SimpleNamespace(
        text=text,
        candidates=(),
        prompt_feedback=None,
        usage_metadata=SimpleNamespace(
            prompt_token_count=17,
            candidates_token_count=5,
        ),
    )

    with pytest.raises(ProviderError) as caught:
        parser.parse_google_genai_audio_response(response, model=MODEL)

    assert type(caught.value) is ProviderError
    assert caught.value.code == expected_code
    assert caught.value.retryable is False
    assert caught.value.details["provider"] == "google"
    assert caught.value.details["model"] == MODEL
    assert caught.value.details["reason"] == expected_reason
    assert caught.value.details["settled_model_usage"] == (
        {
            "model": MODEL,
            "input_count": 17,
            "output_count": 5,
            "unit": "tokens",
        },
    )


def test_google_audio_provider_error_closes_client_and_snapshot(tmp_path, monkeypatch) -> None:
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_short_mp3"
    )
    fake = _FakeGoogleModule(error=ConnectionError("PRIVATE PROVIDER BODY"))
    monkeypatch.setattr(adapter, "load_google_genai", lambda: fake)
    temp_dir = tmp_path / "snapshots"

    with pytest.raises(ProviderError) as caught:
        recognize(FIXTURE, config=_config(temp_dir=temp_dir))

    assert caught.value.code == "PROVIDER_NETWORK"
    assert caught.value.details["provider_calls_attempted"] == 1
    assert "PRIVATE PROVIDER BODY" not in str(caught.value)
    assert fake.clients[0].closed is True
    assert list(temp_dir.glob("ocrllm-audio-*")) == []


def test_google_audio_primary_error_survives_client_close_failure(
    tmp_path,
    monkeypatch,
) -> None:
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_short_mp3"
    )
    fake = _FakeGoogleModule(
        error=ConnectionError("PRIVATE PROVIDER BODY"),
        close_error=RuntimeError("PRIVATE CLOSE BODY"),
    )
    monkeypatch.setattr(adapter, "load_google_genai", lambda: fake)
    temp_dir = tmp_path / "snapshots"

    with pytest.raises(ProviderError) as caught:
        recognize(FIXTURE, config=_config(temp_dir=temp_dir))

    assert caught.value.code == "PROVIDER_NETWORK"
    assert caught.value.details["provider_calls_attempted"] == 1
    assert caught.value.details["provider_client_cleanup_failed"] is True
    assert "PRIVATE PROVIDER BODY" not in str(caught.value)
    assert "PRIVATE CLOSE BODY" not in str(caught.value)
    assert fake.clients[0].closed is False
    assert list(temp_dir.glob("ocrllm-audio-*")) == []


@pytest.mark.parametrize(
    ("close_error", "expected_closed"),
    [
        (None, True),
        (RuntimeError("PRIVATE CLOSE BODY"), False),
    ],
)
def test_google_audio_no_speech_preserves_exact_client_close_outcome(
    close_error,
    expected_closed,
    monkeypatch,
) -> None:
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_short_mp3"
    )
    fake = _FakeGoogleModule(
        text="NOSPEECH4OCRLLM",
        close_error=close_error,
    )
    monkeypatch.setattr(adapter, "load_google_genai", lambda: fake)

    with pytest.raises(NoSpeechDetected) as caught:
        recognize(FIXTURE, config=_config())

    assert caught.value.code == "NO_SPEECH_DETECTED"
    assert caught.value.details["provider"] == "google"
    assert caught.value.details["model"] == MODEL
    assert caught.value.details["provider_calls_attempted"] == 1
    assert caught.value.details["provider_client_closed"] is expected_closed
    assert caught.value.details["settled_model_usage"] == (
        {
            "model": MODEL,
            "input_count": 17,
            "output_count": 5,
            "unit": "tokens",
        },
    )
    assert "remote_file_deleted" not in caught.value.details
    assert caught.value.details.get(
        "provider_client_cleanup_failed",
        False,
    ) is (not expected_closed)
    assert fake.clients[0].closed is expected_closed


@pytest.mark.parametrize(
    ("text", "expected_code"),
    [
        ("NOSPEECH4OCRLLM", "NO_SPEECH_DETECTED"),
        ("  NOSPEECH4OCRLLM\n", "NO_SPEECH_DETECTED"),
        ("nospeech4ocrllm", "NO_SPEECH_DETECTED"),
        ("transcript NOSPEECH4OCRLLM", "PROVIDER_RESPONSE_INVALID"),
        ("transcript NoSpeech4Ocrllm", "PROVIDER_RESPONSE_INVALID"),
        ("", "PROVIDER_RESPONSE_INVALID"),
        ("I'm sorry, I cannot transcribe this.", "PROVIDER_REFUSED_RECOGNITION"),
    ],
)
def test_google_audio_never_accepts_no_speech_empty_or_refusal(
    text, expected_code, monkeypatch
) -> None:
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_short_mp3"
    )
    fake = _FakeGoogleModule(text=text)
    monkeypatch.setattr(adapter, "load_google_genai", lambda: fake)

    expected_type = NoSpeechDetected if expected_code == "NO_SPEECH_DETECTED" else ProviderError
    with pytest.raises(expected_type) as caught:
        recognize(FIXTURE, config=_config())

    assert caught.value.code == expected_code
    assert caught.value.details["provider_calls_attempted"] == 1
    if expected_code == "PROVIDER_REFUSED_RECOGNITION":
        assert caught.value.details["provider"] == "google"
        assert caught.value.details["model"] == MODEL


def test_google_audio_mixed_no_speech_marker_reports_safe_reason(monkeypatch) -> None:
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_short_mp3"
    )
    fake = _FakeGoogleModule(text="transcript NOSPEECH4OCRLLM")
    monkeypatch.setattr(adapter, "load_google_genai", lambda: fake)

    with pytest.raises(ProviderError) as caught:
        recognize(FIXTURE, config=_config())

    assert type(caught.value) is ProviderError
    assert caught.value.code == "PROVIDER_RESPONSE_INVALID"
    assert caught.value.retryable is False
    assert caught.value.details["provider"] == "google"
    assert caught.value.details["model"] == MODEL
    assert caught.value.details["reason"] == "invalid_no_speech_marker"
    assert caught.value.details["provider_calls_attempted"] == 1
    assert "provider_client_cleanup_failed" not in caught.value.details
    assert caught.value.details["settled_model_usage"] == (
        {
            "model": MODEL,
            "input_count": 17,
            "output_count": 5,
            "unit": "tokens",
        },
    )
    assert fake.clients[0].closed is True


def test_google_audio_rejects_groups_and_persistence_options_before_sdk(monkeypatch) -> None:
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_short_mp3"
    )
    loaded = False

    def fail_load():
        nonlocal loaded
        loaded = True
        raise AssertionError("invalid public options must not load SDK")

    monkeypatch.setattr(adapter, "load_google_genai", fail_load)
    with pytest.raises(InvalidSource):
        recognize((FIXTURE, FIXTURE), config=_config())
    for option in (
        {"output_dir": Path("out")},
        {"resume": True, "output_dir": Path("out")},
        {"overwrite": True},
    ):
        with pytest.raises(ConfigError):
            recognize(FIXTURE, config=_config(**option))
    assert loaded is False
