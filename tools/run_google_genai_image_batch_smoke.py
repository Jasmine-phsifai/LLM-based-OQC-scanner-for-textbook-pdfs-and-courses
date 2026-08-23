"""Prove one bounded two-batch Google image recognition run."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ocrllm import (
    Config,
    GoogleGenAISettings,
    RecognitionExecutionPolicy,
    RecognitionPreferences,
    VisionModelSettings,
    recognize_batch,
)
from ocrllm.errors import ConfigError, OCRLLMError


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse exactly two explicit eight-image batches."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--batch",
        action="append",
        required=True,
        type=Path,
        nargs=8,
        metavar="IMAGE",
        help="repeat exactly twice, with eight explicit image paths each time",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    arguments = parser.parse_args(argv)
    if len(arguments.batch) != 2:
        parser.error("--batch must be supplied exactly twice")
    return arguments


def run_google_genai_image_batch_smoke(
    arguments: argparse.Namespace,
) -> dict[str, object]:
    """Run one serial public batch call and return only safe evidence."""
    batches = tuple(tuple(Path(path) for path in batch) for batch in arguments.batch)
    if len(batches) != 2 or any(len(batch) != 8 for batch in batches):
        raise ConfigError(
            "The Google batch live gate requires two batches of eight images.",
            code="CONFIG_INVALID",
        ) from None

    settings = GoogleGenAISettings()
    with tempfile.TemporaryDirectory(prefix="ocrllm-google-batch-") as temporary:
        temporary_root = Path(temporary)
        input_dir = temporary_root / "input"
        output_dir = temporary_root / "output"
        snapshot_dir = temporary_root / "snapshots"
        input_dir.mkdir()
        copied_batches = tuple(
            _copy_batch(batch, input_dir, batch_index=index)
            for index, batch in enumerate(batches, start=1)
        )

        outcomes = recognize_batch(
            copied_batches,
            config=Config(
                provider=settings,
                vision_model=VisionModelSettings(name=arguments.model),
                execution=RecognitionExecutionPolicy(max_parallel_requests=1),
                preferences=RecognitionPreferences(review_passes=0),
                output_dir=output_dir,
                temp_dir=snapshot_dir,
                timeout_seconds=arguments.timeout,
            ),
        )
        if type(outcomes) is not list or len(outcomes) != 2:
            raise ConfigError(
                "The Google batch live gate returned an unexpected outcome count.",
                code="CONFIG_INVALID",
            ) from None
        safe_batches: list[dict[str, object]] = []
        for expected_index, outcome in enumerate(outcomes):
            error = getattr(outcome, "error", None)
            if isinstance(error, OCRLLMError):
                raise error
            if (
                getattr(outcome, "index", None) != expected_index
                or getattr(outcome, "succeeded", False) is not True
                or getattr(outcome, "result", None) is None
            ):
                raise ConfigError(
                    "The Google batch live gate returned an unsuccessful outcome.",
                    code="CONFIG_INVALID",
                ) from None
            safe_batches.append(
                _safe_result_summary(
                    outcome.result,
                    arguments.model,
                    expected_index=expected_index,
                    output_dir=output_dir,
                )
            )

    if temporary_root.exists():
        raise ConfigError(
            "The Google batch live gate temporary directory was not cleaned up.",
            code="CONFIG_INVALID",
        ) from None
    total_calls = sum(item["provider_call_count"] for item in safe_batches)
    if total_calls != 2:
        raise ConfigError(
            "The Google batch live gate did not prove exactly two dispatches.",
            code="CONFIG_INVALID",
        ) from None
    return {
        "status": "passed",
        "model": arguments.model,
        "batch_count": 2,
        "total_provider_call_count": total_calls,
        "batches": safe_batches,
    }


def _copy_batch(
    source_paths: tuple[Path, ...],
    input_dir: Path,
    *,
    batch_index: int,
) -> tuple[Path, ...]:
    copied: list[Path] = []
    for image_index, source_path in enumerate(source_paths, start=1):
        destination = input_dir / (
            f"batch-{batch_index:02d}-image-{image_index:02d}"
            f"{source_path.suffix.lower()}"
        )
        shutil.copyfile(source_path, destination)
        copied.append(destination)
    return tuple(copied)


def _safe_result_summary(
    result: Any,
    model: str,
    *,
    expected_index: int,
    output_dir: Path,
) -> dict[str, object]:
    metadata = getattr(result, "metadata", None)
    output_path = getattr(result, "output_path", None)
    if not isinstance(metadata, Mapping) or output_path is None:
        raise ConfigError(
            "The Google batch live gate returned incomplete result evidence.",
            code="CONFIG_INVALID",
        ) from None
    output_path = Path(output_path)
    slots = metadata.get("workflow_slots")
    if (
        getattr(result, "source_type", None) != "image"
        or getattr(result, "status", None) != "complete"
        or type(getattr(result, "markdown", None)) is not str
        or not result.markdown.strip()
        or output_path.parent != output_dir
        or metadata.get("provider") != "google"
        or metadata.get("model") != model
        or metadata.get("provider_call_count") != 1
        or type(slots) is not tuple
        or len(slots) != 1
        or not isinstance(slots[0], Mapping)
        or slots[0].get("slot_id") != "draft"
        or slots[0].get("workflow_pass") != "draft"
        or slots[0].get("provider") != "google"
        or slots[0].get("model") != model
        or slots[0].get("reused") is not False
        or slots[0].get("provider_calls_attempted") != 1
    ):
        raise ConfigError(
            "The Google batch live gate returned unexpected recognition evidence.",
            code="CONFIG_INVALID",
        ) from None
    usage = metadata.get("current_model_token_usage")
    if (
        type(usage) is not tuple
        or len(usage) != 1
        or not isinstance(usage[0], Mapping)
        or usage[0].get("model") != model
    ):
        raise ConfigError(
            "The Google batch live gate returned unexpected token usage.",
            code="CONFIG_INVALID",
        ) from None
    input_tokens = usage[0].get("input_tokens")
    output_tokens = usage[0].get("output_tokens")
    for token_count in (input_tokens, output_tokens):
        if token_count is not None and (
            type(token_count) is not int or token_count < 0
        ):
            raise ConfigError(
                "The Google batch live gate returned invalid token usage.",
                code="CONFIG_INVALID",
            ) from None
    checkpoint_status = _require_complete_publication(output_path, model)
    return {
        "index": expected_index,
        "provider_call_count": 1,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "published": True,
        "checkpoint_status": checkpoint_status,
    }


def _require_complete_publication(output_path: Path, model: str) -> str:
    state_path = output_path.with_name(f"{output_path.stem}.ocrllm-state.json")
    try:
        document = json.loads(state_path.read_text(encoding="utf-8"))
        slots = document["slots"]
        state_result = document["result"]
        valid = (
            output_path.is_file()
            and document["state_version"] == "ocrllm.image-resume.v2"
            and state_result["status"] == "complete"
            and type(state_result["markdown"]) is str
            and bool(state_result["markdown"].strip())
            and len(slots) == 1
            and slots[0]["slot_id"] == "draft"
            and slots[0]["workflow_pass"] == "draft"
            and slots[0]["provider"] == "google"
            and slots[0]["model"] == model
            and slots[0]["provider_calls_attempted"] == 1
        )
    except Exception:
        valid = False
    if not valid:
        raise ConfigError(
            "The Google batch live gate found an incomplete publication.",
            code="CONFIG_INVALID",
        ) from None
    return "complete"


def _safe_failure_summary(error: OCRLLMError) -> dict[str, object]:
    return {
        "status": "failed",
        "error": {
            "code": error.code,
            "scope": error.details.get("failure_scope"),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    try:
        summary = run_google_genai_image_batch_smoke(arguments)
    except OCRLLMError as error:
        summary = _safe_failure_summary(error)
        print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
        return 1
    except Exception:
        print(
            json.dumps(
                {"status": "failed", "error": {"code": "UNEXPECTED_SAFE_FAILURE"}},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 1
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
