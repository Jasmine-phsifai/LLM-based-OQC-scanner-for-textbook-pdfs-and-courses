"""Failing-first contract for native Google short-MP3 recognition."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

import ocrllm
from ocrllm import AudioModelSettings, Config, GoogleGenAISettings, recognize
from ocrllm.errors import (
    ConfigError,
    InvalidSource,
    NoSpeechDetected,
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
    def __init__(self, models: _Models) -> None:
        self.models = models
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeGoogleModule:
    types = SimpleNamespace(Part=_Part, HttpOptions=_HttpOptions)

    def __init__(self, *, text: str = "synthetic speech", error: Exception | None = None):
        self.models = _Models(text=text, error=error)
        self.clients: list[_Client] = []

    def Client(self, **_kwargs):
        client = _Client(self.models)
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
    assert "PRIVATE PROVIDER BODY" not in str(caught.value)
    assert fake.clients[0].closed is True
    assert list(temp_dir.glob("ocrllm-audio-*")) == []


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
    if expected_code == "PROVIDER_REFUSED_RECOGNITION":
        assert caught.value.details["provider"] == "google"
        assert caught.value.details["model"] == MODEL


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
