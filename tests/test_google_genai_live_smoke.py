from __future__ import annotations

import argparse
import json
from types import MappingProxyType, SimpleNamespace

import pytest

from ocrllm.errors import ConfigError, ProviderError
from tools import run_google_genai_image_smoke as smoke


MODEL = "gemini-live-smoke-model"


def test_live_smoke_requires_exactly_eight_explicit_group_images():
    common = ["--model", MODEL, "--single-image", "one.png", "--group-image"]

    with pytest.raises(SystemExit):
        smoke.parse_arguments([*common, *(f"{index}.png" for index in range(7))])
    with pytest.raises(SystemExit):
        smoke.parse_arguments([*common, *(f"{index}.png" for index in range(9))])

    parsed = smoke.parse_arguments(
        [*common, *(f"{index}.png" for index in range(8))]
    )
    assert len(parsed.group_image) == 8


def test_live_smoke_emits_only_safe_summary(monkeypatch, capsys):
    secret = "unit-test-google-key-never-print"
    markdown = "PRIVATE RECOGNIZED BODY"
    monkeypatch.setenv("GOOGLE_API_KEY", secret)
    calls: list[object] = []

    def fake_list(settings, timeout_seconds):
        if settings.api_key is not None:
            raise ProviderError(
                code="PROVIDER_AUTHENTICATION",
                details={"failure_scope": "credential"},
            )
        assert timeout_seconds == 9.0
        return (MODEL, "another-model")

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

    monkeypatch.setattr(smoke, "list_google_genai_models", fake_list)
    monkeypatch.setattr(smoke, "recognize", fake_recognize)
    arguments = argparse.Namespace(
        model=MODEL,
        single_image="single.png",
        group_image=tuple(f"group-{index}.png" for index in range(8)),
        timeout=9.0,
    )

    assert smoke.main(
        [
            "--model",
            arguments.model,
            "--single-image",
            arguments.single_image,
            "--group-image",
            *arguments.group_image,
            "--timeout",
            str(arguments.timeout),
        ]
    ) == 0

    raw = capsys.readouterr().out.strip()
    payload = json.loads(raw)
    assert payload == {
        "catalog_count": 2,
        "group": {
            "input_tokens": 11,
            "model": MODEL,
            "output_tokens": 7,
            "provider_call_count": 1,
        },
        "invalid_credential": {
            "code": "PROVIDER_AUTHENTICATION",
            "scope": "credential",
        },
        "model": MODEL,
        "single": {
            "input_tokens": 11,
            "model": MODEL,
            "output_tokens": 7,
            "provider_call_count": 1,
        },
        "status": "passed",
    }
    assert len(calls) == 2
    assert len(calls[1]) == 8
    assert secret not in raw
    assert markdown not in raw
    assert "single.png" not in raw
    assert "group-0.png" not in raw


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
