from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from ocrllm import BatchItemOutcome, RecognitionResult
from ocrllm.errors import ConfigError, ProviderUnavailable
from tools import run_google_genai_image_batch_smoke as smoke


MODEL = "gemini-live-batch-model"


def test_batch_smoke_requires_exactly_two_eight_image_batches():
    one_batch = ["--batch", *(f"one-{index}.png" for index in range(8))]
    second_batch = ["--batch", *(f"two-{index}.png" for index in range(8))]

    with pytest.raises(SystemExit):
        smoke.parse_arguments(["--model", MODEL, *one_batch])
    with pytest.raises(SystemExit):
        smoke.parse_arguments(
            ["--model", MODEL, *one_batch, *second_batch, *one_batch]
        )
    with pytest.raises(SystemExit):
        smoke.parse_arguments(
            [
                "--model",
                MODEL,
                "--batch",
                *(f"short-{index}.png" for index in range(7)),
                *second_batch,
            ]
        )

    parsed = smoke.parse_arguments(
        ["--model", MODEL, *one_batch, *second_batch, "--timeout", "9"]
    )
    assert len(parsed.batch) == 2
    assert all(len(batch) == 8 for batch in parsed.batch)
    assert parsed.timeout == 9.0


def test_batch_smoke_uses_exact_tuples_and_emits_only_safe_evidence(
    monkeypatch,
    tmp_path,
):
    secret = "unit-test-google-batch-key-never-print"
    private_markdown = "PRIVATE OCR BATCH TEXT"
    source_paths = tuple(tmp_path / f"private-source-{index}.png" for index in range(8))
    for source_path in source_paths:
        source_path.write_bytes(b"test-image")
    monkeypatch.setenv("GOOGLE_API_KEY", secret)
    observed: dict[str, object] = {}

    def fake_recognize_batch(sources, *, config):
        observed["sources"] = sources
        observed["config"] = config
        assert type(sources) is tuple and len(sources) == 2
        assert all(type(batch) is tuple and len(batch) == 8 for batch in sources)
        assert sources[0][0].stem != sources[1][0].stem
        assert all(path.is_file() for batch in sources for path in batch)
        assert config.execution.max_parallel_requests == 1
        assert config.preferences.review_passes == 0
        assert config.vision_model.name == MODEL
        assert config.timeout_seconds == 9.0

        outcomes = []
        output_dir = config.output_directory()
        output_dir.mkdir(parents=True, exist_ok=True)
        for index, batch in enumerate(sources):
            output_path = output_dir / f"{batch[0].stem}_board.md"
            output_path.write_text(private_markdown, encoding="utf-8")
            state_path = output_path.with_name(
                f"{output_path.stem}.ocrllm-state.json"
            )
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
                            }
                        ],
                        "result": {
                            "status": "complete",
                            "markdown": private_markdown,
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = RecognitionResult(
                markdown=private_markdown,
                source_type="image",
                profile="board",
                output_path=output_path,
                metadata={
                    "provider": "google",
                    "model": MODEL,
                    "provider_call_count": 1,
                    "current_model_token_usage": (
                        {
                            "model": MODEL,
                            "input_tokens": None if index == 0 else 20,
                            "output_tokens": None if index == 0 else 5,
                        },
                    ),
                    "workflow_slots": (
                        {
                            "slot_id": "draft",
                            "workflow_pass": "draft",
                            "provider": "google",
                            "model": MODEL,
                            "reused": False,
                            "provider_calls_attempted": 1,
                        },
                    ),
                },
            )
            outcomes.append(BatchItemOutcome(index=index, result=result))
        return outcomes

    monkeypatch.setattr(smoke, "recognize_batch", fake_recognize_batch)
    arguments = argparse.Namespace(
        model=MODEL,
        batch=(source_paths, tuple(reversed(source_paths))),
        timeout=9.0,
    )

    summary = smoke.run_google_genai_image_batch_smoke(arguments)

    assert summary == {
        "status": "passed",
        "model": MODEL,
        "batch_count": 2,
        "total_provider_call_count": 2,
        "batches": [
            {
                "index": 0,
                "provider_call_count": 1,
                "input_tokens": None,
                "output_tokens": None,
                "published": True,
                "checkpoint_status": "complete",
            },
            {
                "index": 1,
                "provider_call_count": 1,
                "input_tokens": 20,
                "output_tokens": 5,
                "published": True,
                "checkpoint_status": "complete",
            },
        ],
    }
    raw = json.dumps(summary, sort_keys=True, separators=(",", ":"))
    assert secret not in raw
    assert private_markdown not in raw
    assert all(str(path) not in raw for path in source_paths)
    copied_sources = observed["sources"]
    temporary_roots = {path.parent.parent for batch in copied_sources for path in batch}
    assert len(temporary_roots) == 1
    assert all(not root.exists() for root in temporary_roots)


def test_batch_smoke_rejects_false_success_and_cleans_temporary_files(
    monkeypatch,
    tmp_path,
):
    source_paths = tuple(tmp_path / f"source-{index}.png" for index in range(8))
    for source_path in source_paths:
        source_path.write_bytes(b"test-image")
    observed_roots: list[Path] = []

    def fake_recognize_batch(sources, *, config):
        observed_roots.append(sources[0][0].parent.parent)
        bad_result = RecognitionResult(
            markdown="PRIVATE FALSE SUCCESS",
            source_type="image",
            output_path=config.output_directory() / "unpublished.md",
            metadata={
                "provider": "google",
                "model": MODEL,
                "provider_call_count": 2,
                "current_model_token_usage": (
                    {"model": MODEL, "input_tokens": 1, "output_tokens": 1},
                ),
                "workflow_slots": (),
            },
        )
        return [
            BatchItemOutcome(index=0, result=bad_result),
            BatchItemOutcome(index=1, result=bad_result),
        ]

    monkeypatch.setattr(smoke, "recognize_batch", fake_recognize_batch)
    arguments = argparse.Namespace(
        model=MODEL,
        batch=(source_paths, source_paths),
        timeout=9.0,
    )

    with pytest.raises(ConfigError) as caught:
        smoke.run_google_genai_image_batch_smoke(arguments)

    assert caught.value.code == "CONFIG_INVALID"
    assert observed_roots and all(not root.exists() for root in observed_roots)


def test_batch_smoke_main_redacts_provider_text_and_scope(capsys, monkeypatch):
    private_text = "PRIVATE PROVIDER RESPONSE"

    def fail(_arguments):
        raise ProviderUnavailable(
            private_text,
            details={"failure_scope": "provider"},
        )

    monkeypatch.setattr(smoke, "run_google_genai_image_batch_smoke", fail)
    exit_code = smoke.main(
        [
            "--model",
            MODEL,
            "--batch",
            *(f"one-{index}.png" for index in range(8)),
            "--batch",
            *(f"two-{index}.png" for index in range(8)),
        ]
    )

    raw = capsys.readouterr().out
    assert exit_code == 1
    assert json.loads(raw) == {
        "status": "failed",
        "error": {"code": "PROVIDER_UNAVAILABLE", "scope": "provider"},
    }
    assert private_text not in raw
    assert "one-0.png" not in raw
