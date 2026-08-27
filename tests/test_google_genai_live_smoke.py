from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from ocrllm.errors import ConfigError, ProviderError
from tools import run_google_genai_image_smoke as smoke


MODEL = "gemini-live-smoke-model"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_image_live_smoke_cli_rejects_missing_source_without_network(tmp_path):
    environment = os.environ.copy()
    environment.pop("GOOGLE_API_KEY", None)
    environment.pop("GEMINI_API_KEY", None)
    source_path = tmp_path / "never-opened-image-source.png"
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
            str(PROJECT_ROOT / "tools" / "run_google_genai_image_smoke.py"),
            "--model",
            "never-requested-model",
            "--image",
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
            "code": "SOURCE_NOT_FOUND",
            "scope": None,
            "stage": "recognition",
        },
        "status": "failed",
    }
    assert not source_path.exists()


def test_live_smoke_accepts_one_explicit_image():
    parsed = smoke.parse_arguments(["--model", MODEL, "--image", "one.png"])

    assert parsed.image.name == "one.png"


def test_image_live_smoke_delegates_catalog_validation_to_public_recognition(
    monkeypatch,
) -> None:
    assert not hasattr(smoke, "list_google_genai_models")
    monkeypatch.setattr(
        smoke,
        "recognize",
        lambda source, *, config: SimpleNamespace(
            metadata=MappingProxyType(
                {
                    "provider": "google",
                    "model": MODEL,
                    "provider_call_count": 1,
                    "current_model_token_usage": (
                        {"model": MODEL, "input_tokens": 3, "output_tokens": 2},
                    ),
                }
            ),
        ),
    )

    summary = smoke.run_google_genai_image_smoke(
        argparse.Namespace(model=MODEL, image="one.png", timeout=9.0)
    )

    assert summary == {
        "status": "passed",
        "model": MODEL,
        "recognition": {
            "provider_call_count": 1,
            "model": MODEL,
            "input_tokens": 3,
            "output_tokens": 2,
        },
    }


def test_live_smoke_emits_only_safe_summary(monkeypatch, capsys):
    secret = "unit-test-google-key-never-print"
    markdown = "PRIVATE RECOGNIZED BODY"
    monkeypatch.setenv("GOOGLE_API_KEY", secret)
    calls: list[object] = []

    def fake_recognize(source, *, config):
        calls.append(source)
        assert config.vision_model.name == MODEL
        return SimpleNamespace(
            markdown=markdown,
            metadata=MappingProxyType(
                {
                    "provider": "google",
                    "model": MODEL,
                    "provider_call_count": 1,
                    "current_model_token_usage": (
                        {
                            "model": MODEL,
                            "input_tokens": 11,
                            "output_tokens": 7,
                        },
                    ),
                }
            ),
        )

    monkeypatch.setattr(smoke, "recognize", fake_recognize)
    arguments = argparse.Namespace(
        model=MODEL,
        image="single.png",
        timeout=9.0,
    )

    assert smoke.main(
        [
            "--model",
            arguments.model,
            "--image",
            arguments.image,
            "--timeout",
            str(arguments.timeout),
        ]
    ) == 0

    raw = capsys.readouterr().out.strip()
    payload = json.loads(raw)
    assert payload == {
        "model": MODEL,
        "recognition": {
            "input_tokens": 11,
            "model": MODEL,
            "output_tokens": 7,
            "provider_call_count": 1,
        },
        "status": "passed",
    }
    assert [str(call) for call in calls] == ["single.png"]
    assert secret not in raw
    assert markdown not in raw
    assert "single.png" not in raw


def test_image_live_smoke_reports_sanitized_provider_failure_stage(
    monkeypatch, capsys
):
    secret = "PRIVATE-GOOGLE-IMAGE-STAGE-FAILURE"
    source = "private-stage-source.png"

    def failure():
        return ProviderError(
            secret,
            code="PROVIDER_UNAVAILABLE",
            details={
                "failure_scope": "provider",
                "http_status": 400,
                "provider_status": "FAILED_PRECONDITION",
                "raw_response": secret,
            },
        )

    def fake_recognize(actual_source, *, config):
        raise failure()

    monkeypatch.setattr(smoke, "recognize", fake_recognize)

    assert smoke.main(["--model", MODEL, "--image", source]) == 1
    raw = capsys.readouterr().out.strip()
    assert json.loads(raw) == {
        "error": {
            "code": "PROVIDER_UNAVAILABLE",
            "http_status": 400,
            "provider_status": "FAILED_PRECONDITION",
            "scope": "provider",
            "stage": "recognition",
        },
        "status": "failed",
    }
    assert secret not in raw
    assert source not in raw


def test_image_live_smoke_reports_facade_model_failure(monkeypatch, capsys):
    def fail_model_selection(source, *, config):
        raise ProviderError(
            code="PROVIDER_UNAVAILABLE",
            details={"failure_scope": "model", "provider_calls_attempted": 0},
        )

    monkeypatch.setattr(smoke, "recognize", fail_model_selection)

    assert smoke.main(["--model", MODEL, "--image", "private-source.png"]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "error": {
            "code": "PROVIDER_UNAVAILABLE",
            "scope": "model",
            "stage": "recognition",
        },
        "status": "failed",
    }


def test_image_live_smoke_reports_sanitized_unexpected_failure(
    monkeypatch, capsys
):
    secret = "PRIVATE-UNEXPECTED-IMAGE-FAILURE"
    source = "private-unexpected-source.png"

    def raise_unexpected_failure(actual_source, *, config):
        raise RuntimeError(secret)

    monkeypatch.setattr(smoke, "recognize", raise_unexpected_failure)

    assert smoke.main(["--model", MODEL, "--image", source]) == 1
    raw = capsys.readouterr().out.strip()
    assert json.loads(raw) == {
        "error": {
            "code": "UNEXPECTED_SAFE_FAILURE",
            "scope": None,
            "stage": "recognition",
        },
        "status": "failed",
    }
    assert secret not in raw
    assert source not in raw


@pytest.mark.parametrize(
    "metadata",
    (
        {
            "provider": "not-google",
            "model": MODEL,
            "provider_call_count": 1,
            "current_model_token_usage": (
                {"model": MODEL, "input_tokens": 1, "output_tokens": 1},
            ),
        },
        {
            "provider": "google",
            "model": "wrong-model",
            "provider_call_count": 1,
            "current_model_token_usage": (
                {"model": MODEL, "input_tokens": 1, "output_tokens": 1},
            ),
        },
        {
            "provider": "google",
            "model": MODEL,
            "provider_call_count": 2,
            "current_model_token_usage": (
                {"model": MODEL, "input_tokens": 1, "output_tokens": 1},
            ),
        },
        {
            "provider": "google",
            "model": MODEL,
            "provider_call_count": 1,
            "current_model_token_usage": (),
        },
        {
            "provider": "google",
            "model": MODEL,
            "provider_call_count": 1,
            "current_model_token_usage": (
                {"model": MODEL, "input_tokens": 1, "output_tokens": 1},
                {"model": MODEL, "input_tokens": 1, "output_tokens": 1},
            ),
        },
        {
            "provider": "google",
            "model": MODEL,
            "provider_call_count": 1,
            "current_model_token_usage": (
                {"model": "wrong-model", "input_tokens": 1, "output_tokens": 1},
            ),
        },
        {
            "provider": "google",
            "model": MODEL,
            "provider_call_count": 1,
            "current_model_token_usage": (
                {"model": MODEL, "input_tokens": -1, "output_tokens": 1},
            ),
        },
        {
            "provider": "google",
            "model": MODEL,
            "provider_call_count": 1,
            "current_model_token_usage": (
                {"model": MODEL, "input_tokens": True, "output_tokens": 1},
            ),
        },
    ),
)
def test_live_smoke_rejects_unproven_success_metadata(metadata):
    result = SimpleNamespace(metadata=MappingProxyType(metadata))

    with pytest.raises(ConfigError) as captured:
        smoke._safe_recognition_summary(result, MODEL)

    assert captured.value.code == "CONFIG_INVALID"


def test_live_smoke_accepts_missing_but_not_fabricated_usage():
    result = SimpleNamespace(
        metadata=MappingProxyType(
            {
                "provider": "google",
                "model": MODEL,
                "provider_call_count": 1,
                "current_model_token_usage": (
                    {"model": MODEL, "input_tokens": None, "output_tokens": None},
                ),
            }
        )
    )

    assert smoke._safe_recognition_summary(result, MODEL) == {
        "provider_call_count": 1,
        "model": MODEL,
        "input_tokens": None,
        "output_tokens": None,
    }
