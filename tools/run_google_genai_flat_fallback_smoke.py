"""Prove one real serial Google fallback without exposing image content."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType


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
    parser.add_argument("--dashscope-second", action="store_true")
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
    ocrllm = _load_checkout_ocrllm()
    if ocrllm is None:
        return {
            "status": "failed",
            "error": {"code": "PACKAGE_ORIGIN_MISMATCH"},
            "output": _artifact_summary(output_path),
            "state": _artifact_summary(state_path),
        }
    successful_provider = (
        ocrllm.DASHSCOPE_QWEN3_5_OCR_CN_BEIJING
        if getattr(arguments, "dashscope_second", False)
        else ocrllm.GOOGLE_GEMINI_2_5_FLASH
    )
    before: tuple[int, str] | None = None
    try:
        before = _file_fingerprint(image_path)
        result = ocrllm.recognize_images_to_markdown(
            ((image_path,),),
            provider=[_unserved_provider(ocrllm), successful_provider],
            image_task=IMAGE_TASK,
            output_path=output_path,
            timeout_seconds=arguments.timeout,
        )
    except ocrllm.OCRLLMError as error:
        return _error_summary(
            error,
            image_path,
            before,
            output_path,
            state_path,
            successful_provider=successful_provider,
            stable_error_codes=importlib.import_module(
                "ocrllm.errors"
            ).STABLE_ERROR_CODES,
        )
    except Exception:
        return _invalid_summary(output_path, state_path)
    return _result_summary(
        result,
        image_path,
        before,
        output_path,
        state_path,
        successful_provider=successful_provider,
        require_known_tokens=getattr(arguments, "dashscope_second", False),
    )


def _unserved_provider(ocrllm: ModuleType):
    return ocrllm.ProviderModel(
        vendor="google",
        model=UNSERVED_MODEL,
        adapter_id="google_genai",
        settings=ocrllm.GOOGLE_GEMINI_2_5_FLASH.settings,
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
    *,
    successful_provider: object,
    require_known_tokens: bool,
) -> dict[str, object]:
    metadata = getattr(result, "metadata", None)
    warnings = getattr(result, "warnings", None)
    usage = _safe_usage(
        metadata.get("current_provider_model_usage")
        if isinstance(metadata, Mapping)
        else None,
        vendor=getattr(successful_provider, "vendor"),
        model=getattr(successful_provider, "model"),
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
        and (
            not require_known_tokens
            or (
                type(usage["input_tokens"]) is int
                and type(usage["output_tokens"]) is int
            )
        )
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
        "provider": getattr(successful_provider, "vendor"),
        "candidate_providers": ["google", getattr(successful_provider, "vendor")],
        "candidate_models": [UNSERVED_MODEL, getattr(successful_provider, "model")],
        "image_task": IMAGE_TASK,
        "slot_count": 1,
        "settled_slot_count": 1,
        "provider_call_count": 1,
        "provider_failures": [failure],
        "warning_count": 1,
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "sources_unchanged": True,
        "source_size": before[0],
        "source_sha256": before[1],
        "package_origin_is_checkout": True,
        "output": output,
        "state": state,
    }


def _safe_usage(
    value: object,
    *,
    vendor: str,
    model: str,
) -> dict[str, int | None] | None:
    if type(value) is not tuple or len(value) != 1:
        return None
    row = value[0]
    if not isinstance(row, Mapping):
        return None
    calls = row.get("calls")
    input_tokens = row.get("input_tokens")
    output_tokens = row.get("output_tokens")
    if (
        row.get("vendor") != vendor
        or row.get("model") != model
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
    error: object,
    image_path: Path,
    before: tuple[int, str] | None,
    output_path: Path,
    state_path: Path,
    *,
    successful_provider: object,
    stable_error_codes: frozenset[str],
) -> dict[str, object]:
    details = getattr(error, "details")
    calls = details.get("provider_calls_attempted")
    return {
        "status": "failed",
        "error": {
            "code": getattr(error, "code"),
            "scope": _safe_scope(details.get("failure_scope")),
        },
        "package_origin_is_checkout": True,
        "provider_call_count": calls if type(calls) is int and calls >= 0 else None,
        "current_provider_model_usage": _safe_usage(
            details.get("current_provider_model_usage"),
            vendor=getattr(successful_provider, "vendor"),
            model=getattr(successful_provider, "model"),
        ),
        "failed_slots": _safe_terminal_failed_slots(
            details.get("failed_slots"),
            successful_provider=successful_provider,
            stable_error_codes=stable_error_codes,
        ),
        "provider_cleanup_failed": (
            details.get("provider_client_cleanup_failed") is True
            or details.get("provider_client_closed") is False
        ),
        "source_size": before[0] if before is not None else None,
        "source_sha256": before[1] if before is not None else None,
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


def _safe_terminal_failed_slots(
    value: object,
    *,
    successful_provider: object,
    stable_error_codes: frozenset[str],
) -> tuple[dict[str, int | str], ...] | None:
    if type(value) is not tuple or len(value) != 1:
        return None
    row = value[0]
    if not isinstance(row, Mapping):
        return None
    code = row.get("code")
    if (
        row.get("slot_index") != 0
        or row.get("provider") != getattr(successful_provider, "vendor")
        or row.get("model") != getattr(successful_provider, "model")
        or type(code) is not str
        or code not in stable_error_codes
    ):
        return None
    return (
        {
            "slot_index": 0,
            "provider": getattr(successful_provider, "vendor"),
            "model": getattr(successful_provider, "model"),
            "code": code,
        },
    )


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
    summary = run_google_genai_flat_fallback_smoke(parse_arguments(argv))
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0 if summary.get("status") == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
