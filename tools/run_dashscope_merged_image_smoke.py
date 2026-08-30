"""Prove one merged Markdown from two explicit DashScope image batches."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import stat
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType


IMAGE_TASK = "detail_ocr"
SOURCE_COUNT = 2


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Require two explicit images and one new Markdown target."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--resume", action="store_true")
    arguments = parser.parse_args(argv)
    if len(arguments.image) != SOURCE_COUNT:
        parser.error("--image must be supplied exactly twice")
    return arguments


def run_dashscope_merged_image_smoke(
    arguments: argparse.Namespace,
) -> dict[str, object]:
    """Run the public merged owner and return content-free evidence."""
    images = tuple(Path(path).absolute() for path in arguments.image)
    output = Path(arguments.output).absolute()
    state = output.with_name(f"{output.stem}.ocrllm-state.json")
    resume = bool(getattr(arguments, "resume", False))
    ocrllm = _load_checkout_ocrllm()
    if ocrllm is None:
        return {
            "status": "failed",
            "code": "PACKAGE_ORIGIN_MISMATCH",
            "package_origin_is_checkout": False,
            "output": _artifact_summary(output),
            "state": _artifact_summary(state),
        }
    try:
        before = _source_fingerprints(images)
    except (OSError, ValueError):
        return {
            "status": "failed",
            "code": "INVALID_SOURCE_EVIDENCE",
            "output": _artifact_summary(output),
            "state": _artifact_summary(state),
        }
    before_output = _artifact_summary(output)
    before_state = _artifact_summary(state)
    if resume:
        clean_target = (
            before_output.get("exists") is True
            and before_state.get("exists") is True
        )
    else:
        clean_target = (
            before_output.get("exists") is False
            and before_state.get("exists") is False
        )
    if not clean_target:
        return {
            "status": "failed",
            "code": "RESUME_ARTIFACT_MISSING" if resume else "OUTPUT_NOT_CLEAN",
            "operation": "resume" if resume else "recognize",
            "package_origin_is_checkout": True,
            "sources_unchanged": _sources_unchanged(images, before),
            "output": before_output,
            "state": before_state,
        }

    batches = tuple((image,) for image in images)
    try:
        if resume:
            result = ocrllm.resume_images_to_markdown(
                batches,
                provider=ocrllm.DASHSCOPE_QWEN3_5_OCR_CN_BEIJING,
                output_path=output,
                timeout_seconds=arguments.timeout,
            )
        else:
            result = ocrllm.recognize_images_to_markdown(
                batches,
                provider=ocrllm.DASHSCOPE_QWEN3_5_OCR_CN_BEIJING,
                image_task=IMAGE_TASK,
                output_path=output,
                timeout_seconds=arguments.timeout,
            )
    except ocrllm.OCRLLMError as error:
        return _failure_summary(
            error,
            images,
            before=before,
            output=output,
            state=state,
            provider=ocrllm.DASHSCOPE_QWEN3_5_OCR_CN_BEIJING,
            stable_error_codes=importlib.import_module(
                "ocrllm.errors"
            ).STABLE_ERROR_CODES,
            operation="resume" if resume else "recognize",
            before_output=before_output,
            before_state=before_state,
        )
    except Exception:
        return {
            "status": "failed",
            "code": "UNEXPECTED_SAFE_FAILURE",
            "operation": "resume" if resume else "recognize",
            "package_origin_is_checkout": True,
            "sources_unchanged": _sources_unchanged(images, before),
            "output": _artifact_summary(output),
            "state": _artifact_summary(state),
        }

    metadata = result.metadata
    provider = ocrllm.DASHSCOPE_QWEN3_5_OCR_CN_BEIJING
    stable_error_codes = importlib.import_module(
        "ocrllm.errors"
    ).STABLE_ERROR_CODES
    usage = _safe_usage(
        metadata.get("current_provider_model_usage"),
        provider=provider,
    )
    historical_usage = _safe_usage(
        metadata.get("historical_provider_model_usage"),
        provider=provider,
    )
    output_bytes = _read_bytes(output)
    sources_unchanged = _sources_unchanged(images, before)
    state_exists = os.path.lexists(state)
    output_matches_result = (
        output_bytes is not None
        and output_bytes == result.markdown.encode("utf-8")
    )
    expected_current_calls = 1 if resume else SOURCE_COUNT
    expected_reused_slots = 1 if resume else 0
    if resume:
        historical_valid = (
            historical_usage is not None
            and historical_usage["calls"] == SOURCE_COUNT
        )
    else:
        historical_valid = metadata.get("historical_provider_model_usage") == ()
    common_valid = (
        result.source_type == "image"
        and result.profile == IMAGE_TASK
        and result.output_path == output
        and type(result.markdown) is str
        and bool(result.markdown.strip())
        and result.warnings == ()
        and _exact_int(metadata.get("slot_count"), SOURCE_COUNT)
        and _exact_int(metadata.get("reused_slot_count"), expected_reused_slots)
        and _exact_int(metadata.get("provider_call_count"), expected_current_calls)
        and historical_valid
        and metadata.get("provider_failures") is None
        and usage is not None
        and usage["calls"] == expected_current_calls
        and output_matches_result
        and sources_unchanged
    )
    complete = (
        common_valid
        and result.status == "complete"
        and _exact_int(metadata.get("settled_slot_count"), SOURCE_COUNT)
        and metadata.get("failed_slots") is None
        and type(usage["input_tokens"]) is int
        and usage["input_tokens"] >= 0
        and type(usage["output_tokens"]) is int
        and usage["output_tokens"] >= 0
        and not state_exists
        and (
            not resume
            or _artifact_changed(before_output, _artifact_summary(output))
        )
    )
    failed_slots = _safe_failed_slots(
        metadata.get("failed_slots"),
        provider=provider,
        stable_error_codes=stable_error_codes,
    )
    partial = (
        common_valid
        and result.status == "partial"
        and _exact_int(metadata.get("settled_slot_count"), 1)
        and failed_slots is not None
        and len(failed_slots) == 1
        and state_exists
    )
    summary = {
        "status": "passed" if complete else "partial" if partial else "failed",
        "code": None if complete or partial else "INVALID_SCENARIO_EVIDENCE",
        "result_status": result.status,
        "operation": "resume" if resume else "recognize",
        "package_origin_is_checkout": True,
        "provider": provider.vendor,
        "model": provider.model,
        "image_task": IMAGE_TASK,
        "source_count": SOURCE_COUNT,
        "batch_count": SOURCE_COUNT,
        "batch_sizes": (1, 1),
        "source_sizes": tuple(row[0] for row in before),
        "source_sha256s": tuple(row[1] for row in before),
        "provider_call_count": metadata.get("provider_call_count"),
        "reused_slot_count": metadata.get("reused_slot_count"),
        "input_tokens": usage["input_tokens"] if usage is not None else None,
        "output_tokens": usage["output_tokens"] if usage is not None else None,
        "historical_provider_call_count": (
            historical_usage["calls"] if historical_usage is not None else 0
        ),
        "historical_input_tokens": (
            historical_usage["input_tokens"]
            if historical_usage is not None
            else None
        ),
        "historical_output_tokens": (
            historical_usage["output_tokens"]
            if historical_usage is not None
            else None
        ),
        "warning_count": len(result.warnings),
        "sources_unchanged": sources_unchanged,
        "output_matches_result": output_matches_result,
        "output": _artifact_summary(output),
        "state": _artifact_summary(state),
        "before_output": before_output,
        "before_state": before_state,
    }
    if partial:
        summary["failed_slots"] = failed_slots
    return summary


def _failure_summary(
    error: object,
    images: tuple[Path, ...],
    *,
    before: tuple[tuple[int, str], ...],
    output: Path,
    state: Path,
    provider: object,
    stable_error_codes: frozenset[str],
    operation: str,
    before_output: dict[str, object],
    before_state: dict[str, object],
) -> dict[str, object]:
    details = getattr(error, "details")
    return {
        "status": "failed",
        "code": getattr(error, "code"),
        "operation": operation,
        "package_origin_is_checkout": True,
        "provider_call_count": _optional_count(
            details.get("provider_calls_attempted")
        ),
        "current_provider_model_usage": _safe_usage(
            details.get("current_provider_model_usage"),
            provider=provider,
        ),
        "failed_slots": _safe_failed_slots(
            details.get("failed_slots"),
            provider=provider,
            stable_error_codes=stable_error_codes,
        ),
        "source_sizes": tuple(row[0] for row in before),
        "source_sha256s": tuple(row[1] for row in before),
        "sources_unchanged": _sources_unchanged(images, before),
        "provider_cleanup_failed": (
            details.get("provider_client_cleanup_failed") is True
            or details.get("provider_client_closed") is False
        ),
        "output": _artifact_summary(output),
        "state": _artifact_summary(state),
        "before_output": before_output,
        "before_state": before_state,
    }


def _safe_usage(
    value: object,
    *,
    provider: object,
) -> dict[str, int | None] | None:
    if type(value) is not tuple or len(value) != 1 or not isinstance(value[0], Mapping):
        return None
    row = value[0]
    calls = row.get("calls")
    input_tokens = row.get("input_tokens")
    output_tokens = row.get("output_tokens")
    if (
        row.get("vendor") != getattr(provider, "vendor")
        or row.get("model") != getattr(provider, "model")
        or type(calls) is not int
        or calls < 0
        or not _optional_count_is_valid(input_tokens)
        or not _optional_count_is_valid(output_tokens)
    ):
        return None
    return {
        "calls": calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def _safe_failed_slots(
    value: object,
    *,
    provider: object,
    stable_error_codes: frozenset[str],
) -> tuple[dict[str, int | str], ...] | None:
    if type(value) is not tuple:
        return None
    safe: list[dict[str, int | str]] = []
    seen: set[int] = set()
    for item in value:
        if not isinstance(item, Mapping):
            return None
        slot_index = item.get("slot_index")
        code = item.get("code")
        if (
            type(slot_index) is not int
            or not 0 <= slot_index < SOURCE_COUNT
            or slot_index in seen
            or item.get("provider") != getattr(provider, "vendor")
            or item.get("model") != getattr(provider, "model")
            or type(code) is not str
            or code not in stable_error_codes
        ):
            return None
        seen.add(slot_index)
        safe.append({"slot_index": slot_index, "code": code})
    return tuple(sorted(safe, key=lambda row: row["slot_index"]))


def _source_fingerprints(images: tuple[Path, ...]) -> tuple[tuple[int, str], ...]:
    rows: list[tuple[int, str]] = []
    for image in images:
        info = image.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size <= 0:
            raise ValueError
        rows.append((info.st_size, _sha256(image)))
    return tuple(rows)


def _sources_unchanged(
    images: tuple[Path, ...],
    before: tuple[tuple[int, str], ...],
) -> bool:
    try:
        return _source_fingerprints(images) == before
    except (OSError, ValueError):
        return False


def _artifact_summary(path: Path) -> dict[str, object]:
    try:
        if not path.is_file() or path.is_symlink():
            return {"exists": os.path.lexists(path)}
        return {
            "exists": True,
            "size": path.stat().st_size,
            "sha256": _sha256(path),
        }
    except (OSError, ValueError):
        return {"exists": os.path.lexists(path), "inspectable": False}


def _artifact_changed(
    before: dict[str, object],
    after: dict[str, object],
) -> bool:
    return (
        before.get("exists") is True
        and after.get("exists") is True
        and type(before.get("sha256")) is str
        and type(after.get("sha256")) is str
        and before["sha256"] != after["sha256"]
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except (OSError, ValueError):
        return None


def _exact_int(value: object, expected: int) -> bool:
    return type(value) is int and value == expected


def _optional_count(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _optional_count_is_valid(value: object) -> bool:
    return value is None or (type(value) is int and value >= 0)


def _load_checkout_ocrllm() -> ModuleType | None:
    expected = Path(__file__).resolve().parents[1] / "src" / "ocrllm" / "__init__.py"
    try:
        spec = importlib.util.find_spec("ocrllm")
        if spec is None or spec.origin is None:
            return None
        if Path(spec.origin).resolve() != expected:
            return None
        module = importlib.import_module("ocrllm")
        origin = getattr(module, "__file__", None)
        return module if type(origin) is str and Path(origin).resolve() == expected else None
    except (ImportError, OSError, ValueError):
        return None


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    summary = run_dashscope_merged_image_smoke(arguments)
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    return 0 if summary.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
