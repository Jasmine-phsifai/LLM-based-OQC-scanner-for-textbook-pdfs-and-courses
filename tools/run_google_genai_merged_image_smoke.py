"""Prove one merged Markdown from two bounded Google image batches."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from ocrllm import GOOGLE_GEMINI_2_5_FLASH, recognize_images_to_markdown
from ocrllm.errors import OCRLLMError, STABLE_ERROR_CODES


BATCH_COUNT = 2
BATCH_SIZE = 8
IMAGE_TASK = "detail_ocr"


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse exactly two eight-image batches and one explicit output."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch",
        action="append",
        required=True,
        type=Path,
        nargs=BATCH_SIZE,
        metavar="IMAGE",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=600.0)
    arguments = parser.parse_args(argv)
    if len(arguments.batch) != BATCH_COUNT:
        parser.error("--batch must be supplied exactly twice")
    return arguments


def run_google_genai_merged_image_smoke(
    arguments: argparse.Namespace,
) -> dict[str, object]:
    """Run the public merged-image call and return content-free evidence."""
    batches = tuple(tuple(Path(path) for path in batch) for batch in arguments.batch)
    output_path = Path(arguments.output)
    state_path = output_path.with_name(f"{output_path.stem}.ocrllm-state.json")
    before: tuple[tuple[int, str], ...] | None = None
    try:
        before = _source_fingerprints(batches)
        result = recognize_images_to_markdown(
            batches,
            provider=GOOGLE_GEMINI_2_5_FLASH,
            image_task=IMAGE_TASK,
            output_path=output_path,
            timeout_seconds=arguments.timeout,
        )
    except OCRLLMError as error:
        return _failure_summary(error, batches, before, output_path, state_path)
    except Exception:
        return _invalid_summary(output_path, state_path)
    return _result_summary(result, batches, before, output_path, state_path)


def _result_summary(
    result: object,
    batches: tuple[tuple[Path, ...], ...],
    before: tuple[tuple[int, str], ...],
    output_path: Path,
    state_path: Path,
) -> dict[str, object]:
    metadata = getattr(result, "metadata", None)
    output = _artifact_summary(output_path)
    state = _artifact_summary(state_path)
    sources_unchanged = _sources_unchanged(batches, before)
    usage = _safe_usage(metadata.get("current_provider_model_usage")) if isinstance(
        metadata, Mapping
    ) else None
    status = getattr(result, "status", None)
    warnings = getattr(result, "warnings", None)
    valid = (
        status in {"complete", "partial"}
        and getattr(result, "source_type", None) == "image"
        and getattr(result, "profile", None) == IMAGE_TASK
        and getattr(result, "output_path", None) == output_path
        and type(getattr(result, "markdown", None)) is str
        and bool(result.markdown.strip())
        and output.get("exists") is True
        and sources_unchanged
        and type(warnings) is tuple
        and isinstance(metadata, Mapping)
        and metadata.get("slot_count") == BATCH_COUNT
        and metadata.get("reused_slot_count") == 0
        and metadata.get("provider_call_count") == BATCH_COUNT
        and metadata.get("historical_provider_model_usage") == ()
        and usage is not None
        and usage["calls"] == BATCH_COUNT
    )
    if not valid:
        return _invalid_summary(output_path, state_path, result_status=status)

    settled = metadata.get("settled_slot_count")
    summary: dict[str, object] = {
        "provider": "google",
        "model": GOOGLE_GEMINI_2_5_FLASH.model,
        "image_task": IMAGE_TASK,
        "batch_count": BATCH_COUNT,
        "batch_sizes": [BATCH_SIZE, BATCH_SIZE],
        "slot_count": BATCH_COUNT,
        "settled_slot_count": settled,
        "provider_call_count": BATCH_COUNT,
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "sources_unchanged": True,
        "provider_cleanup_warning": bool(warnings),
        "output": output,
        "state": state,
    }
    if status == "complete" and settled == BATCH_COUNT and not warnings and not state[
        "exists"
    ]:
        summary["status"] = "passed"
        return summary
    failed_slots = _safe_failed_slots(metadata.get("failed_slots"))
    if (
        status == "partial"
        and type(settled) is int
        and 0 < settled < BATCH_COUNT
        and failed_slots is not None
        and len(failed_slots) == BATCH_COUNT - settled
        and state["exists"] is True
    ):
        summary["status"] = "partial"
        summary["failed_slot_count"] = len(failed_slots)
        summary["failed_slots"] = failed_slots
        return summary
    return _invalid_summary(output_path, state_path, result_status=status)


def _failure_summary(
    error: OCRLLMError,
    batches: tuple[tuple[Path, ...], ...],
    before: tuple[tuple[int, str], ...] | None,
    output_path: Path,
    state_path: Path,
) -> dict[str, object]:
    summary: dict[str, object] = {
        "status": "failed",
        "error": {
            "code": error.code,
            "scope": _safe_scope(error.details.get("failure_scope")),
        },
        "sources_unchanged": (
            before is not None and _sources_unchanged(batches, before)
        ),
        "output": _artifact_summary(output_path),
        "state": _artifact_summary(state_path),
    }
    calls = error.details.get("provider_calls_attempted")
    if type(calls) is int and calls >= 0:
        summary["provider_call_count"] = calls
    usage = _safe_usage(error.details.get("current_provider_model_usage"))
    if usage is not None:
        summary["provider_model_usage"] = usage
    failed_slots = _safe_failed_slots(error.details.get("failed_slots"))
    if failed_slots is not None:
        summary["failed_slots"] = failed_slots
    return summary


def _safe_usage(value: object) -> dict[str, int | None] | None:
    if type(value) is not tuple or len(value) != 1 or not isinstance(value[0], Mapping):
        return None
    row = value[0]
    calls = row.get("calls")
    input_tokens = row.get("input_tokens")
    output_tokens = row.get("output_tokens")
    if (
        row.get("vendor") != "google"
        or row.get("model") != GOOGLE_GEMINI_2_5_FLASH.model
        or type(calls) is not int
        or calls < 0
        or not _optional_count(input_tokens)
        or not _optional_count(output_tokens)
    ):
        return None
    return {
        "calls": calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def _safe_failed_slots(value: object) -> list[dict[str, int | str]] | None:
    if type(value) is not tuple:
        return None
    safe: list[dict[str, int | str]] = []
    indexes: set[int] = set()
    for row in value:
        if not isinstance(row, Mapping):
            return None
        index = row.get("slot_index")
        code = row.get("code")
        if (
            type(index) is not int
            or not 0 <= index < BATCH_COUNT
            or index in indexes
            or type(code) is not str
            or code not in STABLE_ERROR_CODES
            or row.get("provider") != "google"
            or row.get("model") != GOOGLE_GEMINI_2_5_FLASH.model
        ):
            return None
        indexes.add(index)
        safe.append({"slot_index": index, "code": code})
    return safe


def _source_fingerprints(
    batches: tuple[tuple[Path, ...], ...],
) -> tuple[tuple[int, str], ...]:
    return tuple(_file_fingerprint(path) for batch in batches for path in batch)


def _sources_unchanged(
    batches: tuple[tuple[Path, ...], ...],
    before: tuple[tuple[int, str], ...],
) -> bool:
    try:
        return _source_fingerprints(batches) == before
    except (OSError, ValueError):
        return False


def _file_fingerprint(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _artifact_summary(path: Path) -> dict[str, object]:
    try:
        if not path.is_file():
            return {"exists": False}
        size, digest = _file_fingerprint(path)
    except (OSError, ValueError):
        return {"exists": None}
    return {"exists": True, "size": size, "sha256": digest}


def _invalid_summary(
    output_path: Path,
    state_path: Path,
    *,
    result_status: object = None,
) -> dict[str, object]:
    return {
        "status": "failed",
        "error": {"code": "INCOMPLETE_LIVE_EVIDENCE"},
        "result_status": (
            result_status if result_status in {"complete", "partial"} else None
        ),
        "output": _artifact_summary(output_path),
        "state": _artifact_summary(state_path),
    }


def _optional_count(value: object) -> bool:
    return value is None or (type(value) is int and value >= 0)


def _safe_scope(value: object) -> str | None:
    if type(value) is str and value in {
        "request",
        "credential",
        "model",
        "account",
        "provider",
    }:
        return value
    return None


def main(argv: Sequence[str] | None = None) -> int:
    summary = run_google_genai_merged_image_smoke(parse_arguments(argv))
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0 if summary.get("status") == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
