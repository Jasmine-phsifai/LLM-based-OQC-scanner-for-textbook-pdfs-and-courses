"""Prove one two-image batch through a compatible provider preset."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path


PROVIDER_NAMES = ("dashscope", "google")


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Require one provider, two images, and one new Markdown target."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=PROVIDER_NAMES, required=True)
    parser.add_argument("--image", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=120.0)
    arguments = parser.parse_args(argv)
    if len(arguments.image) != 2:
        parser.error("--image must be supplied exactly twice")
    return arguments


def run_openai_compatible_image_smoke(
    arguments: argparse.Namespace,
) -> dict[str, object]:
    """Run the public planner and merged owner, returning content-free evidence."""
    ocrllm = _load_checkout_ocrllm()
    if ocrllm is None:
        return _failure("PACKAGE_ORIGIN_MISMATCH")
    images = tuple(Path(path).absolute() for path in arguments.image)
    output = Path(arguments.output).absolute()
    state = output.with_name(f"{output.stem}.ocrllm-state.json")
    before = _source_fingerprints(images)
    if before is None:
        return _failure("INVALID_SOURCE_EVIDENCE")
    if os.path.lexists(output) or os.path.lexists(state):
        return _failure(
            "OUTPUT_NOT_CLEAN",
            sources_unchanged=_sources_unchanged(images, before),
        )
    provider = _provider(ocrllm, arguments.provider)

    try:
        batches = ocrllm.batchify_images(images, provider=provider)
        result = ocrllm.recognize_images_to_markdown(
            batches,
            provider=provider,
            image_task="detail_ocr",
            output_path=output,
            timeout_seconds=arguments.timeout,
        )
    except ocrllm.OCRLLMError as error:
        details = error.details
        return _failure(
            error.code,
            provider=provider.vendor,
            model=provider.model,
            provider_calls_attempted=_safe_count(
                details.get("provider_calls_attempted")
            ),
            input_tokens=_safe_token(details.get("input_tokens")),
            output_tokens=_safe_token(details.get("output_tokens")),
            sources_unchanged=_sources_unchanged(images, before),
            output_exists=os.path.lexists(output),
            state_exists=os.path.lexists(state),
        )
    except Exception:
        return _failure(
            "UNEXPECTED_SAFE_FAILURE",
            sources_unchanged=_sources_unchanged(images, before),
            output_exists=os.path.lexists(output),
            state_exists=os.path.lexists(state),
        )

    usage = result.metadata.get("current_provider_model_usage")
    usage_row = usage[0] if type(usage) is tuple and len(usage) == 1 else None
    output_bytes = _read_bytes(output)
    passed = (
        type(batches) is tuple
        and len(batches) == 1
        and type(batches[0]) is tuple
        and batches[0] == images
        and result.status == "complete"
        and result.source_type == "image"
        and result.output_path == output
        and result.warnings == ()
        and _safe_count(result.metadata.get("provider_call_count")) == 1
        and _safe_count(result.metadata.get("slot_count")) == 1
        and _safe_count(result.metadata.get("settled_slot_count")) == 1
        and _safe_count(result.metadata.get("reused_slot_count")) == 0
        and result.metadata.get("historical_provider_model_usage") == ()
        and isinstance(usage_row, Mapping)
        and usage_row.get("vendor") == provider.vendor
        and usage_row.get("model") == provider.model
        and _safe_count(usage_row.get("calls")) == 1
        and _safe_token(usage_row.get("input_tokens")) is not None
        and _safe_token(usage_row.get("output_tokens")) is not None
        and output_bytes == result.markdown.encode("utf-8")
        and not os.path.lexists(state)
        and _sources_unchanged(images, before)
    )
    return {
        "status": "passed" if passed else "failed",
        "code": None if passed else "INVALID_SCENARIO_EVIDENCE",
        "package_origin_is_checkout": True,
        "provider": provider.vendor,
        "model": provider.model,
        "source_count": len(images),
        "source_sizes": tuple(row[0] for row in before),
        "source_sha256s": tuple(row[1] for row in before),
        "batch_count": len(batches),
        "batch_sizes": tuple(len(batch) for batch in batches),
        "provider_call_count": result.metadata.get("provider_call_count"),
        "input_tokens": (
            _safe_token(usage_row.get("input_tokens"))
            if isinstance(usage_row, Mapping)
            else None
        ),
        "output_tokens": (
            _safe_token(usage_row.get("output_tokens"))
            if isinstance(usage_row, Mapping)
            else None
        ),
        "output_byte_size": len(output_bytes) if output_bytes is not None else None,
        "output_sha256": (
            hashlib.sha256(output_bytes).hexdigest()
            if output_bytes is not None
            else None
        ),
        "state_exists": os.path.lexists(state),
        "sources_unchanged": _sources_unchanged(images, before),
    }


def _load_checkout_ocrllm():
    expected = Path(__file__).resolve().parents[1] / "src" / "ocrllm" / "__init__.py"
    spec = importlib.util.find_spec("ocrllm")
    if spec is None or spec.origin is None:
        return None
    try:
        if Path(spec.origin).resolve() != expected.resolve():
            return None
        import ocrllm

        if Path(ocrllm.__file__).resolve() != expected.resolve():
            return None
    except (ImportError, OSError, ValueError):
        return None
    return ocrllm


def _provider(ocrllm, name: str):
    if name == "google":
        return ocrllm.GOOGLE_GEMINI_2_5_FLASH_OPENAI_COMPATIBLE
    return ocrllm.DASHSCOPE_QWEN3_5_OCR_OPENAI_COMPATIBLE_CN_BEIJING


def _source_fingerprints(images: tuple[Path, ...]):
    rows = []
    try:
        for image in images:
            if image.is_symlink() or not image.is_file():
                return None
            source_bytes = image.read_bytes()
            rows.append((len(source_bytes), hashlib.sha256(source_bytes).hexdigest()))
    except (OSError, ValueError):
        return None
    return tuple(rows)


def _sources_unchanged(images: tuple[Path, ...], before: object) -> bool:
    return _source_fingerprints(images) == before


def _read_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes() if path.is_file() and not path.is_symlink() else None
    except (OSError, ValueError):
        return None


def _safe_count(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _safe_token(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _failure(code: str, **facts: object) -> dict[str, object]:
    return {
        "status": "failed",
        "code": code,
        "package_origin_is_checkout": code != "PACKAGE_ORIGIN_MISMATCH",
        **facts,
    }


def main(argv: Sequence[str] | None = None) -> int:
    summary = run_openai_compatible_image_smoke(parse_arguments(argv))
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    return 0 if summary.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
