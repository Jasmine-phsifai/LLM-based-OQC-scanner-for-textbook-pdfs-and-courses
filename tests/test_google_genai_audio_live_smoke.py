from __future__ import annotations

import json
from types import MappingProxyType, SimpleNamespace

import pytest

from ocrllm.errors import ConfigError, ProviderError
from tools import run_google_genai_audio_smoke as smoke


MODEL = "gemini-audio-live-model"


def test_audio_live_smoke_outputs_no_transcript_path_or_secret(monkeypatch, capsys):
    secret = "unit-test-google-audio-secret"
    transcript = "PRIVATE AUDIO TRANSCRIPT"
    source = "private-audio-name.mp3"
    monkeypatch.setenv("GOOGLE_API_KEY", secret)

    def fake_list(settings, timeout_seconds):
        if settings.api_key is not None:
            raise ProviderError(
                code="PROVIDER_AUTHENTICATION",
                details={"failure_scope": "credential"},
            )
        assert timeout_seconds == 9.0
        return (MODEL,)

    def fake_recognize(actual_source, *, config):
        assert str(actual_source) == source
        assert config.audio_model.name == MODEL
        return SimpleNamespace(
            markdown=transcript,
            source_type="audio",
            output_path=None,
            metadata=MappingProxyType(
                {
                    "provider": "google",
                    "model": MODEL,
                    "provider_call_count": 1,
                    "duration_seconds": 1.25,
                    "byte_size": 2048,
                    "current_model_token_usage": (
                        {"model": MODEL, "input_tokens": 21, "output_tokens": 8},
                    ),
                }
            ),
        )

    monkeypatch.setattr(smoke, "list_google_genai_models", fake_list)
    monkeypatch.setattr(smoke, "recognize", fake_recognize)

    assert smoke.main(
        ["--model", MODEL, "--audio", source, "--timeout", "9"]
    ) == 0
    raw = capsys.readouterr().out.strip()
    assert json.loads(raw) == {
        "catalog_count": 1,
        "invalid_credential": {
            "code": "PROVIDER_AUTHENTICATION",
            "scope": "credential",
        },
        "model": MODEL,
        "recognition": {
            "input_tokens": 21,
            "model": MODEL,
            "output_tokens": 8,
            "provider_call_count": 1,
        },
        "status": "passed",
    }
    assert secret not in raw
    assert transcript not in raw
    assert source not in raw


def test_audio_live_summary_rejects_unproven_result_or_source_evidence():
    base_metadata = {
        "provider": "google",
        "model": MODEL,
        "provider_call_count": 1,
        "duration_seconds": 1.0,
        "byte_size": 10,
        "current_model_token_usage": (
            {"model": MODEL, "input_tokens": None, "output_tokens": None},
        ),
    }
    invalid_results = (
        SimpleNamespace(
            source_type="image",
            output_path=None,
            metadata=MappingProxyType(base_metadata),
        ),
        SimpleNamespace(
            source_type="audio",
            output_path="unexpected.md",
            metadata=MappingProxyType(base_metadata),
        ),
        SimpleNamespace(
            source_type="audio",
            output_path=None,
            metadata=MappingProxyType({**base_metadata, "duration_seconds": float("nan")}),
        ),
        SimpleNamespace(
            source_type="audio",
            output_path=None,
            metadata=MappingProxyType({**base_metadata, "byte_size": True}),
        ),
    )

    for result in invalid_results:
        with pytest.raises(ConfigError):
            smoke._safe_recognition_summary(result, MODEL)
