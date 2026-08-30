"""Prove one real serial Google fallback without exposing image content."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from ocrllm import GOOGLE_GEMINI_2_5_FLASH, ProviderModel
from ocrllm import recognize_images_to_markdown
from ocrllm.errors import OCRLLMError


UNSERVED_MODEL = "ocrllm-intentionally-unserved-flat-fallback-probe"
IMAGE_TASK = "detail_ocr"
FALLBACK_WARNING = (
    "Recognition completed after one or more provider candidates failed."
)


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse one image, one explicit output, and one operation timeout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=600.0)
    return parser.parse_args(argv)


def run_google_genai_flat_fallback_smoke(
    arguments: argparse.Namespace,
) -> dict[str, object]:
    """Run one public flat lane and return only content-free evidence."""
    image_path = Path(arguments.image)
    output_path = Path(arguments.output)
    state_path = output_path.with_name(
        f"{output_path.stem}.ocrllm-state.json"
    )
    before: tuple[int, str] | None = None
    try:
        before = _file_fingerprint(image_path)
        result = recognize_images_to_markdown(
            ((image_path,),),
            provider=[_unserved_provider(), GOOGLE_GEMINI_2_5_FLASH],
            image_task=IMAGE_TASK,
            output_path=output_path,
            timeout_seconds=arguments.timeout,
        )
    except OCRLLMError as error:
        return _error_summary(error, image_path, before, output_path, state_path)
    except Exception:
        return _invalid_summary(output_path, state_path)
    return _result_summary(
        result,
        image_path,
        before,
        output_path,
        state_path,
    )


def _unserved_provider() -> ProviderModel:
    return ProviderModel(
        vendor="google",
        model=UNSERVED_MODEL,
        adapter_id="google_genai",
        settings=GOOGLE_GEMINI_2_5_FLASH.settings,
        supports_plain_ocr=True,
        supports_detail_ocr=True,
        supports_audio=False,
        default_image_batch_size=1,
        default_audio_minutes=None,
        retry_rules={},
    )


def _result_summary(
    result: object,
    image_path: Path,
    before: tuple[int, str],
    output_path: Path,
    state_path: Path,
) -> dict[str, object]:
    metadata = getattr(result, "metadata", None)
    warnings = getattr(result, "warnings", None)
    usage = _safe_usage(
        metadata.get("current_provider_model_usage")
        if isinstance(metadata, Mapping)
        else None
    )
    failure = _safe_failure(
        metadata.get("provider_failures")
        if isinstance(metadata, Mapping)
        else None
    )
    output = _artifact_summary(output_path)
    state = _artifact_summary(state_path)
    valid = (
        getattr(result, "status", None) == "complete"
        and getattr(result, "source_type", None) == "image"
        and getattr(result, "profile", None) == IMAGE_TASK
        and getattr(result, "output_path", None) == output_path
        and type(getattr(result, "markdown", None)) is str
        and bool(result.markdown.strip())
        and warnings == (FALLBACK_WARNING,)
        and isinstance(metadata, Mapping)
        and metadata.get("slot_count") == 1
        and metadata.get("settled_slot_count") == 1
        and metadata.get("reused_slot_count") == 0
        and metadata.get("provider_call_count") == 1
        and metadata.get("historical_provider_model_usage") == ()
        and usage is not None
        and usage["calls"] == 1
        and failure is not None
        and output.get("exists") is True
        and _markdown_matches_output(result.markdown, output_path)
        and state.get("exists") is False
        and _source_unchanged(image_path, before)
    )
    if not valid:
        return _invalid_summary(
            output_path,
            state_path,
            result_status=getattr(result, "status", None),
        )
    return {
        "status": "passed",
        "provider": "google",
        "candidate_models": [UNSERVED_MODEL, GOOGLE_GEMINI_2_5_FLASH.model],
        "image_task": IMAGE_TASK,
        "slot_count": 1,
        "settled_slot_count": 1,
        "provider_call_count": 1,
        "provider_failures": [failure],
        "warning_count": 1,
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "sources_unchanged": True,
        "output": output,
        "state": state,
    }


def _safe_usage(value: object) -> dict[str, int | None] | None:
    if type(value) is not tuple or len(value) != 1:
        return None
    row = value[0]
    if not isinstance(row, Mapping):
        return None
    calls = row.get("calls")
    input_tokens = row.get("input_tokens")
    output_tokens = row.get("output_tokens")
    if (
        row.get("vendor") != "google"
        or row.get("model") != GOOGLE_GEMINI_2_5_FLASH.model
        or calls != 1
        or not _optional_count(input_tokens)
        or not _optional_count(output_tokens)
    ):
        return None
    return {
        "calls": calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def _safe_failure(value: object) -> dict[str, int | str] | None:
    if type(value) is not tuple or len(value) != 1:
        return None
    row = value[0]
    if not isinstance(row, Mapping):
        return None
    description = row.get("description")
    if (
        row.get("slot_index") != 0
        or row.get("vendor") != "google"
        or row.get("model") != UNSERVED_MODEL
        or row.get("code") != "PROVIDER_UNAVAILABLE"
        or type(description) is not str
        or not description
        or len(description) > 512
    ):
        return None
    return {
        "slot_index": 0,
        "provider": "google",
        "model": UNSERVED_MODEL,
        "code": "PROVIDER_UNAVAILABLE",
    }


def _error_summary(
    error: OCRLLMError,
    image_path: Path,
    before: tuple[int, str] | None,
    output_path: Path,
    state_path: Path,
) -> dict[str, object]:
    calls = error.details.get("provider_calls_attempted")
    return {
        "status": "failed",
        "error": {
            "code": error.code,
            "scope": _safe_scope(error.details.get("failure_scope")),
        },
        "provider_call_count": calls if type(calls) is int and calls >= 0 else None,
        "sources_unchanged": (
            before is not None and _source_unchanged(image_path, before)
        ),
        "output": _artifact_summary(output_path),
        "state": _artifact_summary(state_path),
    }


def _file_fingerprint(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _source_unchanged(path: Path, before: tuple[int, str]) -> bool:
    try:
        return _file_fingerprint(path) == before
    except (OSError, ValueError):
        return False


def _artifact_summary(path: Path) -> dict[str, object]:
    try:
        if not path.is_file():
            return {"exists": False}
        size, digest = _file_fingerprint(path)
    except (OSError, ValueError):
        return {"exists": None}
    return {"exists": True, "size": size, "sha256": digest}


def _markdown_matches_output(markdown: str, output_path: Path) -> bool:
    try:
        return output_path.read_bytes() == markdown.encode("utf-8")
    except (OSError, UnicodeError, ValueError):
        return False


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
    summary = run_google_genai_flat_fallback_smoke(parse_arguments(argv))
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0 if summary.get("status") == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
