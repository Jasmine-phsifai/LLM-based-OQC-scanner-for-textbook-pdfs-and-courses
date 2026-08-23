from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from ocrllm.errors import Cancelled, ConfigError
from tools import run_google_genai_image_resume_smoke as smoke


MODEL = "gemini-live-resume-model"


def test_resume_smoke_requires_exactly_eight_explicit_images():
    common = ["--model", MODEL, "--image"]

    with pytest.raises(SystemExit):
        smoke.parse_arguments([*common, *(f"{index}.png" for index in range(7))])
    with pytest.raises(SystemExit):
        smoke.parse_arguments([*common, *(f"{index}.png" for index in range(9))])

    parsed = smoke.parse_arguments(
        [*common, *(f"{index}.png" for index in range(8))]
    )
    assert len(parsed.image) == 8


def test_resume_smoke_emits_only_safe_checkpoint_and_usage_summary(
    monkeypatch, tmp_path
):
    secret = "unit-test-google-resume-key-never-print"
    markdown = "PRIVATE CHECKPOINT MARKDOWN"
    source_paths = tuple(tmp_path / f"source-{index}.png" for index in range(8))
    for source_path in source_paths:
        source_path.write_bytes(b"test-image")
    monkeypatch.setenv("GOOGLE_API_KEY", secret)
    calls: list[object] = []

    def fake_recognize(source, *, config):
        calls.append((source, config))
        if not config.resume:
            state_path = config.output_directory() / "image-01_plus_7_board.ocrllm-state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(
                json.dumps(
                    {
                        "state_version": "ocrllm.image-resume.v2",
                        "slots": [
                            {
                                "slot_id": "draft",
                                "workflow_pass": "draft",
                                "provider": "google",
                                "model": MODEL,
                                "provider_calls_attempted": 1,
                                "markdown": markdown,
                            }
                        ],
                        "result": {"status": "partial", "markdown": ""},
                    }
                ),
                encoding="utf-8",
            )
            assert config.cancellation.is_set() is True
            raise Cancelled(
                details={
                    "workflow_pass": "review",
                    "provider_calls_attempted": 1,
                    "settled_model_usage": (
                        {
                            "model": MODEL,
                            "input_count": 12,
                            "output_count": 3,
                            "unit": "tokens",
                        },
                    ),
                }
            )
        state_path = config.output_directory() / "image-01_plus_7_board.ocrllm-state.json"
        state_path.write_text(
            json.dumps(
                {
                    "state_version": "ocrllm.image-resume.v2",
                    "slots": [
                        {
                            "slot_id": "draft",
                            "workflow_pass": "draft",
                            "provider": "google",
                            "model": MODEL,
                            "provider_calls_attempted": 1,
                        },
                        {
                            "slot_id": "review",
                            "workflow_pass": "review",
                            "provider": "google",
                            "model": MODEL,
                            "provider_calls_attempted": 1,
                        },
                    ],
                    "result": {"status": "complete", "markdown": markdown},
                }
            ),
            encoding="utf-8",
        )
        output_path = config.output_directory() / "image-01_plus_7_board.md"
        output_path.write_text(markdown, encoding="utf-8")
        return SimpleNamespace(
            markdown=markdown,
            source_type="image",
            output_path=output_path,
            metadata=MappingProxyType(
                {
                    "provider": "google",
                    "model": MODEL,
                    "provider_call_count": 1,
                    "current_model_token_usage": (
                        {"model": MODEL, "input_tokens": 20, "output_tokens": 5},
                    ),
                    "workflow_slots": (
                        {
                            "slot_id": "draft",
                            "workflow_pass": "draft",
                            "provider": "google",
                            "model": MODEL,
                            "reused": True,
                            "provider_calls_attempted": 0,
                        },
                        {
                            "slot_id": "review",
                            "workflow_pass": "review",
                            "provider": "google",
                            "model": MODEL,
                            "reused": False,
                            "provider_calls_attempted": 1,
                        },
                    ),
                }
            ),
        )

    monkeypatch.setattr(smoke, "recognize", fake_recognize)
    arguments = argparse.Namespace(model=MODEL, image=source_paths, timeout=9.0)

    summary = smoke.run_google_genai_image_resume_smoke(arguments)

    raw = json.dumps(summary, sort_keys=True, separators=(",", ":"))
    assert summary == {
        "status": "passed",
        "model": MODEL,
        "interrupted": {
            "code": "CANCELLED",
            "provider_call_count": 1,
            "input_tokens": 12,
            "output_tokens": 3,
        },
        "partial": {"slot_count": 1, "status": "partial"},
        "resumed": {
            "checkpoint_status": "complete",
            "output_published": True,
            "provider_call_count": 1,
            "reused_slot_count": 1,
            "fresh_slot_count": 1,
            "input_tokens": 20,
            "output_tokens": 5,
        },
    }
    assert len(calls) == 2
    assert secret not in raw
    assert markdown not in raw
    assert all(str(source_path) not in raw for source_path in source_paths)
    temporary_roots = {
        Path(source[0]).parent.parent
        for source, _config in calls
    }
    assert len(temporary_roots) == 1
    assert all(not root.exists() for root in temporary_roots)


@pytest.mark.parametrize(
    "bad_result",
    (
        SimpleNamespace(metadata=MappingProxyType({})),
        SimpleNamespace(
            metadata=MappingProxyType(
                {
                    "provider": "google",
                    "model": MODEL,
                    "provider_call_count": 2,
                    "current_model_token_usage": (),
                    "workflow_slots": (),
                }
            )
        ),
    ),
)
def test_resume_smoke_rejects_unproven_resume_success(bad_result):
    with pytest.raises(ConfigError):
        smoke._safe_resumed_summary(bad_result, MODEL)
