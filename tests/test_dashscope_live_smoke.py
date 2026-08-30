from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from ocrllm.errors import ConfigError, ProviderError
from ocrllm.providers.provider_model import ProviderModel
from ocrllm.providers.vision_provider_response import VisionProviderResponse
from tools import run_dashscope_image_smoke as smoke


MODEL = "qwen-current-bounded-model"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _metadata(**updates):
    metadata = {
        "provider": "dashscope",
        "model": MODEL,
        "provider_region": "cn-beijing",
        "provider_call_count": 1,
        "current_model_token_usage": (
            {"model": MODEL, "input_tokens": 11, "output_tokens": 7},
        ),
        "model_attempts": (
            {
                "model": MODEL,
                "outcome": "success",
                "provider_calls_attempted": 1,
            },
        ),
        "workflow_slots": (
            {
                "slot_id": "draft",
                "workflow_pass": "draft",
                "provider": "dashscope",
                "model": MODEL,
                "reused": False,
                "provider_calls_attempted": 1,
            },
        ),
    }
    metadata.update(updates)
    return MappingProxyType(metadata)


def test_dashscope_live_smoke_cli_reports_missing_credential_without_image_io(tmp_path):
    environment = os.environ.copy()
    environment.pop("DASHSCOPE_API_KEY", None)
    source_path = tmp_path / "never-opened.png"
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")

    completed = subprocess.run(
        (
            sys.executable,
            str(PROJECT_ROOT / "tools" / "run_dashscope_image_smoke.py"),
            "--model",
            MODEL,
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
        "error": {"code": "CONFIG_MISSING", "scope": None, "stage": "catalog"},
        "status": "failed",
    }
    assert not source_path.exists()


def test_dashscope_live_smoke_emits_only_safe_one_call_summary(monkeypatch, capsys):
    secret = "unit-test-dashscope-key-never-print"
    markdown = "PRIVATE RECOGNIZED BODY"
    monkeypatch.setenv("DASHSCOPE_API_KEY", secret)
    calls: list[object] = []

    def fake_catalog(settings):
        assert settings.api_key is None
        assert settings.region == "cn-beijing"
        return frozenset((MODEL, "another-model"))

    def fake_recognize(source, *, config):
        calls.append(source)
        assert config.vision_model.name == MODEL
        assert config.provider.api_key is None
        assert config.timeout_seconds == 9.0
        return SimpleNamespace(
            status="complete",
            markdown=markdown,
            metadata=_metadata(),
        )

    monkeypatch.setattr(smoke, "fetch_dashscope_model_catalog", fake_catalog)
    monkeypatch.setattr(smoke, "recognize", fake_recognize)

    assert smoke.main(
        ["--model", MODEL, "--image", "single.png", "--timeout", "9"]
    ) == 0
    raw = capsys.readouterr().out.strip()
    assert json.loads(raw) == {
        "catalog_count": 2,
        "model": MODEL,
        "recognition": {
            "client_closed": True,
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


def test_dashscope_live_smoke_can_exercise_private_provider_model(monkeypatch, capsys):
    secret = "unit-test-dashscope-key-never-print"
    markdown = "PRIVATE RECOGNIZED BODY"
    monkeypatch.setenv("DASHSCOPE_API_KEY", secret)
    calls: list[tuple[object, ...]] = []

    monkeypatch.setattr(
        smoke,
        "fetch_dashscope_model_catalog",
        lambda settings: frozenset((MODEL, "another-model")),
    )

    def fake_provider_model_call(
        provider_model, image_paths, *, prompt, timeout_seconds
    ):
        assert type(provider_model) is ProviderModel
        assert provider_model.vendor == "dashscope"
        assert provider_model.model == MODEL
        assert provider_model.adapter_id == "dashscope_openai_compatible"
        assert provider_model.settings.api_key is None
        assert prompt
        assert timeout_seconds == 9.0
        calls.append(tuple(image_paths))
        return VisionProviderResponse(
            markdown=markdown,
            input_tokens=11,
            output_tokens=7,
        )

    monkeypatch.setattr(
        smoke,
        "recognize_provider_model_images",
        fake_provider_model_call,
    )

    assert smoke.main(
        [
            "--model",
            MODEL,
            "--image",
            "single.png",
            "--timeout",
            "9",
            "--provider-model",
        ]
    ) == 0
    raw = capsys.readouterr().out.strip()
    assert json.loads(raw) == {
        "catalog_count": 2,
        "model": MODEL,
        "recognition": {
            "client_closed": True,
            "input_tokens": 11,
            "model": MODEL,
            "output_tokens": 7,
            "provider_call_count": 1,
        },
        "runtime_path": "provider_model",
        "status": "passed",
    }
    assert calls == [(Path("single.png"),)]
    assert secret not in raw
    assert markdown not in raw
    assert "single.png" not in raw


def test_dashscope_live_smoke_missing_model_makes_zero_recognition_calls(
    monkeypatch, capsys
):
    monkeypatch.setattr(
        smoke,
        "fetch_dashscope_model_catalog",
        lambda settings: frozenset(("another-model",)),
    )
    monkeypatch.setattr(
        smoke,
        "recognize",
        lambda *args, **kwargs: pytest.fail("recognition must not start"),
    )

    assert smoke.main(["--model", MODEL, "--image", "private.png"]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "error": {"code": "CONFIG_INVALID", "scope": None, "stage": "model_selection"},
        "status": "failed",
    }


@pytest.mark.parametrize("failure_stage", ("catalog", "recognition"))
def test_dashscope_live_smoke_sanitizes_provider_failures(
    failure_stage, monkeypatch, capsys
):
    secret = "PRIVATE-DASHSCOPE-FAILURE"

    def fail():
        return ProviderError(
            secret,
            code="PROVIDER_UNAVAILABLE",
            details={"failure_scope": "provider", "raw_response": secret},
        )

    def fake_catalog(settings):
        if failure_stage == "catalog":
            raise fail()
        return frozenset((MODEL,))

    def fake_recognize(source, *, config):
        raise fail()

    monkeypatch.setattr(smoke, "fetch_dashscope_model_catalog", fake_catalog)
    monkeypatch.setattr(smoke, "recognize", fake_recognize)

    assert smoke.main(["--model", MODEL, "--image", "private.png"]) == 1
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
    assert "private.png" not in raw


@pytest.mark.parametrize(
    "status,updates",
    (
        ("partial", {}),
        ("complete", {"provider": "google"}),
        ("complete", {"model": "wrong-model"}),
        ("complete", {"provider_call_count": 2}),
        ("complete", {"model_attempts": ()}),
        ("complete", {"workflow_slots": ()}),
        ("complete", {"provider_client_closed": False}),
        ("complete", {"current_model_token_usage": ()}),
        (
            "complete",
            {
                "current_model_token_usage": (
                    {"model": "wrong-model", "input_tokens": 1, "output_tokens": 1},
                )
            },
        ),
    ),
)
def test_dashscope_live_smoke_rejects_unproven_success(status, updates):
    result = SimpleNamespace(status=status, metadata=_metadata(**updates))

    with pytest.raises(ConfigError) as captured:
        smoke._safe_recognition_summary(result, MODEL)

    assert captured.value.code == "CONFIG_INVALID"


@pytest.mark.parametrize(
    "response",
    (
        "plain string",
        VisionProviderResponse(markdown="ok", client_closed=False),
    ),
)
def test_dashscope_live_smoke_rejects_unproven_provider_model_success(response):
    with pytest.raises(ConfigError) as captured:
        smoke._safe_provider_model_summary(response, MODEL)

    assert captured.value.code == "CONFIG_INVALID"
