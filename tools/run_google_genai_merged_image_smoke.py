"""Prove one merged Markdown from two bounded Google image batches."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from ocrllm import (
    GOOGLE_GEMINI_2_5_FLASH,
    recognize_images_to_markdown,
    repair_images_to_markdown,
    resume_images_to_markdown,
)
from ocrllm.errors import OCRLLMError, STABLE_ERROR_CODES
from ocrllm.providers.provider_model import ProviderModel


BATCH_COUNT = 2
BATCH_SIZE = 8
IMAGE_TASK = "detail_ocr"
UNSERVED_REPAIR_MODEL = "ocrllm-deliberately-unserved-repair"


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
    parser.add_argument(
        "--resume",
        action="store_true",
        help="resume the supplied output instead of starting a fresh job",
    )
    parser.add_argument(
        "--nested-lanes",
        action="store_true",
        help="run the fixed fresh two-lane provider-pool scenario",
    )
    parser.add_argument(
        "--repair",
        action="store_true",
        help="run one fixed partial-state-loss then marker-repair scenario",
    )
    arguments = parser.parse_args(argv)
    if len(arguments.batch) != BATCH_COUNT:
        parser.error("--batch must be supplied exactly twice")
    if arguments.resume and arguments.nested_lanes:
        parser.error("the fixed nested-lane live scenario is fresh-only")
    if arguments.repair and (arguments.resume or arguments.nested_lanes):
        parser.error("the fixed repair scenario is separate from resume/nested modes")
    return arguments


def run_google_genai_merged_image_smoke(
    arguments: argparse.Namespace,
) -> dict[str, object]:
    """Run the public merged-image call and return content-free evidence."""
    batches = tuple(tuple(Path(path) for path in batch) for batch in arguments.batch)
    output_path = Path(arguments.output)
    state_path = output_path.with_name(f"{output_path.stem}.ocrllm-state.json")
    if arguments.repair:
        return _run_repair_scenario(
            batches,
            output_path=output_path,
            state_path=state_path,
            timeout_seconds=arguments.timeout,
        )
    before: tuple[tuple[int, str], ...] | None = None
    provider = (
        [[GOOGLE_GEMINI_2_5_FLASH], [GOOGLE_GEMINI_2_5_FLASH]]
        if arguments.nested_lanes
        else GOOGLE_GEMINI_2_5_FLASH
    )
    try:
        before = _source_fingerprints(batches)
        if arguments.resume:
            result = resume_images_to_markdown(
                batches,
                provider=provider,
                output_path=output_path,
                timeout_seconds=arguments.timeout,
            )
        else:
            result = recognize_images_to_markdown(
                batches,
                provider=provider,
                image_task=IMAGE_TASK,
                output_path=output_path,
                timeout_seconds=arguments.timeout,
            )
    except OCRLLMError as error:
        summary = _failure_summary(
            error,
            batches,
            before,
            output_path,
            state_path,
            resume=arguments.resume,
            nested_lanes=arguments.nested_lanes,
        )
    except Exception:
        return _invalid_summary(output_path, state_path)
    return _result_summary(
        result,
        batches,
        before,
        output_path,
        state_path,
        resume=arguments.resume,
        nested_lanes=arguments.nested_lanes,
    )


def _run_repair_scenario(
    batches: tuple[tuple[Path, ...], ...],
    *,
    output_path: Path,
    state_path: Path,
    timeout_seconds: float,
) -> dict[str, object]:
    before: tuple[tuple[int, str], ...] | None = None
    try:
        before = _source_fingerprints(batches)
        partial = recognize_images_to_markdown(
            batches,
            provider=[
                [GOOGLE_GEMINI_2_5_FLASH],
                [_unserved_repair_provider()],
            ],
            image_task=IMAGE_TASK,
            output_path=output_path,
            timeout_seconds=timeout_seconds,
        )
    except OCRLLMError as error:
        return _repair_failure_summary(
            error,
            batches,
            before,
            output_path,
            state_path,
            stage="fresh",
        )
    except Exception:
        return {
            **_invalid_summary(output_path, state_path),
            "operation": "repair",
            "stage": "fresh",
        }

    valid_partial, partial_usage, partial_failed = _validate_fresh_repair_partial(
        partial,
        batches=batches,
        before=before,
        output_path=output_path,
        state_path=state_path,
    )
    if not valid_partial:
        return {
            **_invalid_summary(
                output_path,
                state_path,
                result_status=getattr(partial, "status", None),
            ),
            "operation": "repair",
            "stage": "fresh_partial",
            "failed_slot": partial_failed,
            "sources_unchanged": _sources_unchanged(batches, before),
        }
    assert partial_usage is not None
    partial_output = _artifact_summary(output_path)
    try:
        state_path.unlink()
    except (OSError, ValueError):
        return _repair_state_loss_failure(
            batches,
            before=before,
            output_path=output_path,
            state_path=state_path,
            partial_output=partial_output,
        )
    if os.path.lexists(state_path):
        return _repair_state_loss_failure(
            batches,
            before=before,
            output_path=output_path,
            state_path=state_path,
            partial_output=partial_output,
        )

    try:
        repaired = repair_images_to_markdown(
            batches,
            provider=GOOGLE_GEMINI_2_5_FLASH,
            image_task=IMAGE_TASK,
            output_path=output_path,
            timeout_seconds=timeout_seconds,
        )
    except OCRLLMError as error:
        return _repair_failure_summary(
            error,
            batches,
            before,
            output_path,
            state_path,
            stage="repair",
        )
    except Exception:
        return {
            **_invalid_summary(output_path, state_path),
            "operation": "repair",
            "stage": "repair",
        }

    return _finish_repair_scenario(
        repaired,
        batches=batches,
        before=before,
        output_path=output_path,
        state_path=state_path,
        partial_output=partial_output,
        partial_usage=partial_usage,
    )


def _validate_fresh_repair_partial(
    partial,
    *,
    batches: tuple[tuple[Path, ...], ...],
    before: tuple[tuple[int, str], ...],
    output_path: Path,
    state_path: Path,
) -> tuple[
    bool,
    dict[str, int | None] | None,
    dict[str, int | str] | None,
]:
    metadata = partial.metadata
    usage = _safe_usage(metadata.get("current_provider_model_usage"))
    failed = _strict_repair_failed_slot(
        metadata.get("failed_slots"),
        model=UNSERVED_REPAIR_MODEL,
        code="PROVIDER_UNAVAILABLE",
    )
    output_bytes = _read_file_bytes(output_path)
    valid = (
        partial.status == "partial"
        and partial.source_type == "image"
        and partial.profile == IMAGE_TASK
        and partial.output_path == output_path
        and type(partial.markdown) is str
        and bool(partial.markdown.strip())
        and partial.warnings == ()
        and _is_exact_int(metadata.get("slot_count"), BATCH_COUNT)
        and _is_exact_int(metadata.get("settled_slot_count"), 1)
        and _is_exact_int(metadata.get("reused_slot_count"), 0)
        and _is_exact_int(metadata.get("provider_call_count"), 1)
        and metadata.get("historical_provider_model_usage") == ()
        and metadata.get("provider_failures") is None
        and usage is not None
        and usage["calls"] == 1
        and failed is not None
        and output_bytes is not None
        and output_bytes == partial.markdown.encode("utf-8")
        and state_path.is_file()
        and not state_path.is_symlink()
        and _sources_unchanged(batches, before)
    )
    return valid, usage, failed


def _repair_state_loss_failure(
    batches: tuple[tuple[Path, ...], ...],
    *,
    before: tuple[tuple[int, str], ...],
    output_path: Path,
    state_path: Path,
    partial_output: dict[str, object],
) -> dict[str, object]:
    return {
        "status": "failed",
        "error": {"code": "INCOMPLETE_LIVE_EVIDENCE"},
        "operation": "repair",
        "stage": "state_loss",
        "partial_output": partial_output,
        "state_exists": os.path.lexists(state_path),
        "sources_unchanged": _sources_unchanged(batches, before),
        "output": _artifact_summary(output_path),
    }


def _finish_repair_scenario(
    repaired,
    *,
    batches: tuple[tuple[Path, ...], ...],
    before: tuple[tuple[int, str], ...],
    output_path: Path,
    state_path: Path,
    partial_output: dict[str, object],
    partial_usage: dict[str, int | None],
) -> dict[str, object]:
    metadata = repaired.metadata
    usage = _safe_usage(metadata.get("current_provider_model_usage"))
    output_bytes = _read_file_bytes(output_path)
    final_output = _artifact_summary(output_path)
    state_exists = os.path.lexists(state_path)
    sources_unchanged = _sources_unchanged(batches, before)
    common = {
        "operation": "repair",
        "provider": "google",
        "model": GOOGLE_GEMINI_2_5_FLASH.model,
        "image_task": IMAGE_TASK,
        "batch_count": BATCH_COUNT,
        "batch_sizes": [BATCH_SIZE, BATCH_SIZE],
        "fresh_provider_call_count": 1,
        "fresh_provider_usage": partial_usage,
        "repair_provider_call_count": metadata.get("provider_call_count"),
        "repair_provider_usage": usage,
        "warning_count": len(repaired.warnings),
        "sources_unchanged": sources_unchanged,
        "partial_output": partial_output,
        "output": final_output,
        "output_matches_result": (
            output_bytes is not None
            and output_bytes == repaired.markdown.encode("utf-8")
        ),
        "state_exists": state_exists,
    }
    valid_complete = (
        repaired.status == "complete"
        and repaired.source_type == "image"
        and repaired.profile == IMAGE_TASK
        and repaired.output_path == output_path
        and repaired.warnings == ()
        and _is_exact_int(metadata.get("slot_count"), BATCH_COUNT)
        and _is_exact_int(metadata.get("repair_marker_count"), 1)
        and _is_exact_int(metadata.get("repaired_slot_count"), 1)
        and _is_exact_int(metadata.get("settled_slot_count"), BATCH_COUNT)
        and _is_exact_int(metadata.get("provider_call_count"), 1)
        and metadata.get("failed_slots") is None
        and metadata.get("provider_failures") is None
        and usage is not None
        and usage["calls"] == 1
        and "OCRLLM_FAILED_IMAGE_SLOT" not in repaired.markdown
        and final_output.get("exists") is True
        and common["output_matches_result"] is True
        and final_output != partial_output
        and state_exists is False
        and sources_unchanged
    )
    if valid_complete:
        return {"status": "passed", **common}

    failed = _strict_repair_failed_slot(
        metadata.get("failed_slots"),
        model=GOOGLE_GEMINI_2_5_FLASH.model,
        code=None,
    )
    calls = metadata.get("provider_call_count")
    valid_partial = (
        repaired.status == "partial"
        and repaired.source_type == "image"
        and repaired.profile == IMAGE_TASK
        and repaired.output_path == output_path
        and _valid_partial_warnings(repaired.warnings)
        and _is_exact_int(metadata.get("slot_count"), BATCH_COUNT)
        and _is_exact_int(metadata.get("repair_marker_count"), 1)
        and _is_exact_int(metadata.get("repaired_slot_count"), 0)
        and _is_exact_int(metadata.get("settled_slot_count"), 1)
        and type(calls) is int
        and calls >= 0
        and (calls == 0 or (usage is not None and usage["calls"] == calls))
        and failed is not None
        and metadata.get("provider_failures") is None
        and "OCRLLM_FAILED_IMAGE_SLOT" in repaired.markdown
        and final_output.get("exists") is True
        and common["output_matches_result"] is True
        and state_exists is False
        and sources_unchanged
    )
    if valid_partial:
        return {
            "status": "partial",
            **common,
            "failed_slot_count": 1,
            "failed_slots": (failed,),
            "provider_cleanup_warning": _has_cleanup_warning(repaired.warnings),
        }
    return {
        **_invalid_summary(
            output_path,
            state_path,
            result_status=getattr(repaired, "status", None),
        ),
        "operation": "repair",
        "stage": "repair_result",
        "sources_unchanged": sources_unchanged,
    }


def _repair_failure_summary(
    error: OCRLLMError,
    batches: tuple[tuple[Path, ...], ...],
    before: tuple[tuple[int, str], ...] | None,
    output_path: Path,
    state_path: Path,
    *,
    stage: str,
) -> dict[str, object]:
    summary = _failure_summary(
        error,
        batches,
        before,
        output_path,
        state_path,
        resume=False,
        nested_lanes=False,
    )
    summary.update(
        {
            "operation": "repair",
            "provider_mode": "repair",
            "stage": stage,
            "state_exists": os.path.lexists(state_path),
            "provider_cleanup_failed": _provider_cleanup_failed(error),
            "provider_client_closed": _optional_bool(
                error.details.get("provider_client_closed")
            ),
            "snapshot_cleanup_failed": _optional_bool(
                error.details.get("snapshot_cleanup_failed")
            ),
        }
    )
    return summary


def _unserved_repair_provider() -> ProviderModel:
    return ProviderModel(
        vendor=GOOGLE_GEMINI_2_5_FLASH.vendor,
        model=UNSERVED_REPAIR_MODEL,
        adapter_id=GOOGLE_GEMINI_2_5_FLASH.adapter_id,
        settings=GOOGLE_GEMINI_2_5_FLASH.settings,
        supports_plain_ocr=True,
        supports_detail_ocr=True,
        supports_audio=False,
        default_image_batch_size=BATCH_SIZE,
        default_audio_minutes=None,
        retry_rules={},
    )


def _result_summary(
    result: object,
    batches: tuple[tuple[Path, ...], ...],
    before: tuple[tuple[int, str], ...],
    output_path: Path,
    state_path: Path,
    *,
    resume: bool,
    nested_lanes: bool,
) -> dict[str, object]:
    metadata = getattr(result, "metadata", None)
    output = _artifact_summary(output_path)
    state = _artifact_summary(state_path)
    sources_unchanged = _sources_unchanged(batches, before)
    usage = None
    historical_usage = None
    if isinstance(metadata, Mapping):
        usage = _safe_usage(metadata.get("current_provider_model_usage"))
        historical_usage = _safe_usage(
            metadata.get("historical_provider_model_usage")
        )
    expected_calls = 1 if resume else BATCH_COUNT
    expected_reused = 1 if resume else 0
    if resume:
        valid_history = (
            historical_usage is not None
            and historical_usage["calls"] == BATCH_COUNT
        )
    else:
        valid_history = (
            isinstance(metadata, Mapping)
            and metadata.get("historical_provider_model_usage") == ()
        )
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
        and metadata.get("reused_slot_count") == expected_reused
        and metadata.get("provider_call_count") == expected_calls
        and valid_history
        and usage is not None
        and usage["calls"] == expected_calls
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
        "operation": "resume" if resume else "recognize",
        "provider_mode": "nested" if nested_lanes else "scalar",
        "lane_count": 2 if nested_lanes else 1,
        "slot_count": BATCH_COUNT,
        "settled_slot_count": settled,
        "reused_slot_count": expected_reused,
        "provider_call_count": expected_calls,
        "historical_provider_call_count": (
            historical_usage["calls"] if historical_usage is not None else 0
        ),
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
    *,
    resume: bool,
    nested_lanes: bool,
) -> dict[str, object]:
    summary: dict[str, object] = {
        "status": "failed",
        "operation": "resume" if resume else "recognize",
        "provider_mode": "nested" if nested_lanes else "scalar",
        "lane_count": 2 if nested_lanes else 1,
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


def _strict_repair_failed_slot(
    value: object,
    *,
    model: str,
    code: str | None,
) -> dict[str, int | str] | None:
    if type(value) is not tuple or len(value) != 1:
        return None
    row = value[0]
    if not isinstance(row, Mapping):
        return None
    index = row.get("slot_index")
    actual_code = row.get("code")
    if (
        type(index) is not int
        or index != 1
        or row.get("provider") != "google"
        or row.get("model") != model
        or type(actual_code) is not str
        or actual_code not in STABLE_ERROR_CODES
        or (code is not None and actual_code != code)
    ):
        return None
    return {
        "slot_index": 1,
        "provider": "google",
        "model": model,
        "code": actual_code,
    }


def _read_file_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes() if path.is_file() else None
    except (OSError, ValueError):
        return None


def _is_exact_int(value: object, expected: int) -> bool:
    return type(value) is int and value == expected


def _optional_bool(value: object) -> bool | None:
    return value if type(value) is bool else None


def _provider_cleanup_failed(error: OCRLLMError) -> bool:
    return bool(
        error.details.get("provider_client_cleanup_failed") is True
        or error.details.get("provider_client_closed") is False
    )


def _has_cleanup_warning(warnings: tuple[str, ...]) -> bool:
    return any(
        warning
        in {
            "At least one provider client could not be closed during image repair.",
            "At least one temporary image snapshot could not be removed after repair.",
        }
        for warning in warnings
    )


def _valid_partial_warnings(warnings: object) -> bool:
    required = "One or more image slots remain failed after repair."
    allowed = {
        required,
        "At least one provider client could not be closed during image repair.",
        "At least one temporary image snapshot could not be removed after repair.",
    }
    return (
        type(warnings) is tuple
        and all(type(warning) is str for warning in warnings)
        and required in warnings
        and len(warnings) == len(set(warnings))
        and all(warning in allowed for warning in warnings)
    )


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
