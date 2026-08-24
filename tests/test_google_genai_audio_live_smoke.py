from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from ocrllm.errors import ConfigError, InvalidSource, ProviderError
from tools import run_google_genai_audio_smoke as smoke


MODEL = "gemini-audio-live-model"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_audio_live_smoke_cli_reports_missing_credential_without_network(tmp_path):
    environment = os.environ.copy()
    environment.pop("GOOGLE_API_KEY", None)
    environment.pop("GEMINI_API_KEY", None)
    source_path = tmp_path / "never-opened-audio-source.mp3"
    source_pythonpath = str(PROJECT_ROOT / "src")
    inherited_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        os.pathsep.join((source_pythonpath, inherited_pythonpath))
        if inherited_pythonpath
        else source_pythonpath
    )

    completed = subprocess.run(
        (
            sys.executable,
            str(PROJECT_ROOT / "tools" / "run_google_genai_audio_smoke.py"),
            "--model",
            "never-requested-model",
            "--audio",
            str(source_path),
        ),
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 1
    assert completed.stderr == ""
    assert json.loads(completed.stdout) == {
        "error": {
            "code": "CONFIG_MISSING",
            "scope": None,
            "stage": "catalog",
        },
        "status": "failed",
    }
    assert not source_path.exists()


def test_audio_live_smoke_outputs_no_transcript_path_or_secret(monkeypatch, capsys):
    secret = "unit-test-google-audio-secret"
    transcript = "PRIVATE AUDIO TRANSCRIPT"
    source = "private-audio-name.mp3"
    list_api_keys = []
    monkeypatch.setenv("GOOGLE_API_KEY", secret)

    def fake_list(settings, timeout_seconds):
        list_api_keys.append(settings.api_key)
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
        "model": MODEL,
        "recognition": {
            "input_tokens": 21,
            "model": MODEL,
            "output_tokens": 8,
            "provider_call_count": 1,
        },
        "status": "passed",
    }
    assert list_api_keys == [None]
    assert secret not in raw
    assert transcript not in raw
    assert source not in raw


@pytest.mark.parametrize("failure_stage", ["catalog", "recognition"])
def test_audio_live_smoke_reports_sanitized_provider_failure_stage(
    failure_stage, monkeypatch, capsys
):
    secret = "PRIVATE-GOOGLE-STAGE-FAILURE"
    source = "private-stage-source.mp3"

    def failure():
        return ProviderError(
            secret,
            code="PROVIDER_UNAVAILABLE",
            details={"failure_scope": "provider", "raw_response": secret},
        )

    def fake_list(settings, timeout_seconds):
        if failure_stage == "catalog":
            raise failure()
        return (MODEL,)

    def fake_recognize(actual_source, *, config):
        raise failure()

    monkeypatch.setattr(smoke, "list_google_genai_models", fake_list)
    monkeypatch.setattr(smoke, "recognize", fake_recognize)

    assert smoke.main(["--model", MODEL, "--audio", source]) == 1
    raw = capsys.readouterr().out.strip()
    assert json.loads(raw) == {
        "error": {
            "code": "PROVIDER_UNAVAILABLE",
            "scope": "provider",
            "stage": failure_stage,
        },
        "status": "failed",
    }
    assert secret not in raw
    assert source not in raw


def test_audio_live_smoke_reports_missing_model_selection_stage(monkeypatch, capsys):
    monkeypatch.setattr(
        smoke,
        "list_google_genai_models",
        lambda settings, timeout_seconds: ("another-model",),
    )

    assert smoke.main(["--model", MODEL, "--audio", "private-source.mp3"]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "error": {
            "code": "CONFIG_INVALID",
            "scope": None,
            "stage": "model_selection",
        },
        "status": "failed",
    }


def test_audio_live_smoke_reports_sanitized_source_failure(monkeypatch, capsys):
    secret = "PRIVATE-SOURCE-FAILURE"
    source = "private-missing-source.mp3"

    def raise_source_failure(actual_source, *, config):
        raise InvalidSource(secret, code="SOURCE_NOT_FOUND")

    monkeypatch.setattr(
        smoke,
        "list_google_genai_models",
        lambda settings, timeout_seconds: (MODEL,),
    )
    monkeypatch.setattr(smoke, "recognize", raise_source_failure)

    assert smoke.main(["--model", MODEL, "--audio", source]) == 1
    raw = capsys.readouterr().out.strip()
    assert json.loads(raw) == {
        "error": {
            "code": "SOURCE_NOT_FOUND",
            "scope": None,
            "stage": "recognition",
        },
        "status": "failed",
    }
    assert secret not in raw
    assert source not in raw


@pytest.mark.parametrize("failure_stage", ["catalog", "recognition"])
def test_audio_live_smoke_reports_sanitized_unexpected_failure(
    failure_stage, monkeypatch, capsys
):
    secret = "PRIVATE-UNEXPECTED-FAILURE"
    source = "private-unexpected-source.mp3"

    def fake_list(settings, timeout_seconds):
        if failure_stage == "catalog":
            raise RuntimeError(secret)
        return (MODEL,)

    def raise_unexpected_failure(actual_source, *, config):
        raise RuntimeError(secret)

    monkeypatch.setattr(smoke, "list_google_genai_models", fake_list)
    monkeypatch.setattr(smoke, "recognize", raise_unexpected_failure)

    assert smoke.main(["--model", MODEL, "--audio", source]) == 1
    raw = capsys.readouterr().out.strip()
    assert json.loads(raw) == {
        "error": {
            "code": "UNEXPECTED_SAFE_FAILURE",
            "scope": None,
            "stage": failure_stage,
        },
        "status": "failed",
    }
    assert secret not in raw
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
