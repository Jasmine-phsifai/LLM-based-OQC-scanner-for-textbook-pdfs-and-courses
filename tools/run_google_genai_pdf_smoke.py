"""Prove one bounded 16-page Google PDF recognition run."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ocrllm import (
    Config,
    GOOGLE_GEMINI_2_5_FLASH,
    GoogleGenAISettings,
    RecognitionExecutionPolicy,
    RecognitionPreferences,
    VisionModelSettings,
    batchify_images,
    extract_pdf_pages,
    list_google_genai_models,
    recognize,
    recognize_images_to_markdown,
)
from ocrllm.errors import ConfigError, OCRLLMError


PDF_PAGE_COUNT = 16
ROUTE_A_BATCH_SIZE = 8
ROUTE_A_IMAGE_TASK = "detail_ocr"


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse one model and exactly 16 explicit authorized page images."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--page-image",
        action="append",
        required=True,
        type=Path,
        help="repeat exactly 16 times in desired PDF page order",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--route-a", action="store_true")
    arguments = parser.parse_args(argv)
    if len(arguments.page_image) != PDF_PAGE_COUNT:
        parser.error("--page-image must be supplied exactly 16 times")
    return arguments


def run_google_genai_pdf_smoke(arguments: argparse.Namespace) -> dict[str, object]:
    """Run one public PDF request and return content-free evidence."""
    page_images = tuple(Path(path) for path in arguments.page_image)
    if len(page_images) != PDF_PAGE_COUNT:
        raise ConfigError(
            "The Google PDF live gate requires exactly 16 page images.",
            code="CONFIG_INVALID",
        ) from None
    route_a = getattr(arguments, "route_a", False)
    if route_a and arguments.model != GOOGLE_GEMINI_2_5_FLASH.model:
        raise ConfigError(
            "The Route A PDF live gate uses the proven Google preset.",
            code="CONFIG_INVALID",
        ) from None
    source_fingerprints = _file_fingerprints(page_images)
    settings = GoogleGenAISettings()
    catalog = list_google_genai_models(settings, arguments.timeout)
    if arguments.model not in catalog:
        raise ConfigError(
            "The selected Google PDF live model is not currently served.",
            code="CONFIG_INVALID",
        ) from None

    with tempfile.TemporaryDirectory(prefix="ocrllm-google-pdf-") as temporary:
        temporary_root = Path(temporary)
        pdf_path = temporary_root / "input.pdf"
        output_directory = temporary_root / "output"
        snapshot_directory = temporary_root / "snapshots"
        _build_pdf_from_images(page_images, pdf_path)
        pdf_fingerprint = _file_fingerprint(pdf_path)
        if route_a:
            safe_result = _run_route_a_pdf_smoke(
                pdf_path,
                model=arguments.model,
                output_directory=output_directory,
                temporary_root=temporary_root,
                timeout_seconds=arguments.timeout,
            )
        else:
            result = recognize(
                pdf_path,
                config=Config(
                    provider=settings,
                    vision_model=VisionModelSettings(name=arguments.model),
                    execution=RecognitionExecutionPolicy(max_parallel_requests=4),
                    preferences=RecognitionPreferences(review_passes=0),
                    output_dir=output_directory,
                    temp_dir=snapshot_directory,
                    timeout_seconds=arguments.timeout,
                ),
            )
            safe_result = _safe_pdf_result_summary(
                result,
                model=arguments.model,
                output_directory=output_directory,
            )
        if (
            _file_fingerprint(pdf_path) != pdf_fingerprint
            or _file_fingerprints(page_images) != source_fingerprints
        ):
            _raise_invalid_result()

    if temporary_root.exists():
        raise ConfigError(
            "The Google PDF live gate temporary directory was not cleaned up.",
            code="CONFIG_INVALID",
        ) from None
    return {
        "status": "passed",
        "route": "route_a" if route_a else "direct",
        "model": arguments.model,
        "catalog_count": len(catalog),
        "source_images_unchanged": True,
        "pdf_source_unchanged": True,
        "temporary_root_cleaned": True,
        **safe_result,
    }


def _run_route_a_pdf_smoke(
    pdf_path: Path,
    *,
    model: str,
    output_directory: Path,
    temporary_root: Path,
    timeout_seconds: float,
) -> dict[str, object]:
    page_directory = temporary_root / "pages"
    page_paths = extract_pdf_pages(pdf_path, output_dir=page_directory)
    expected_paths = tuple(
        page_directory / f"page-{page_number:06d}.png"
        for page_number in range(1, PDF_PAGE_COUNT + 1)
    )
    if page_paths != expected_paths or not all(path.is_file() for path in page_paths):
        _raise_invalid_result()
    page_fingerprints = _file_fingerprints(page_paths)
    batches = batchify_images(
        tuple(page_paths),
        batch_size=ROUTE_A_BATCH_SIZE,
    )
    if (
        len(batches) != 2
        or tuple(len(batch) for batch in batches) != (8, 8)
        or tuple(path for batch in batches for path in batch) != page_paths
    ):
        _raise_invalid_result()
    output_directory.mkdir()
    output_path = output_directory / "input_board.md"
    result = recognize_images_to_markdown(
        batches,
        provider=GOOGLE_GEMINI_2_5_FLASH,
        image_task=ROUTE_A_IMAGE_TASK,
        output_path=output_path,
        timeout_seconds=timeout_seconds,
    )
    summary = _safe_route_a_result_summary(
        result,
        model=model,
        output_path=output_path,
        page_paths=page_paths,
        batches=batches,
    )
    if _file_fingerprints(page_paths) != page_fingerprints:
        _raise_invalid_result()
    return summary


def _safe_route_a_result_summary(
    result: Any,
    *,
    model: str,
    output_path: Path,
    page_paths: tuple[Path, ...],
    batches: tuple[tuple[Path, ...], ...],
) -> dict[str, object]:
    metadata = getattr(result, "metadata", None)
    markdown = getattr(result, "markdown", None)
    warnings = getattr(result, "warnings", None)
    usage = _safe_route_a_usage(
        metadata.get("current_provider_model_usage")
        if isinstance(metadata, Mapping)
        else None,
        model=model,
    )
    state_path = output_path.with_name(f"{output_path.stem}.ocrllm-state.json")
    if (
        getattr(result, "source_type", None) != "image"
        or getattr(result, "profile", None) != ROUTE_A_IMAGE_TASK
        or getattr(result, "status", None) != "complete"
        or getattr(result, "output_path", None) != output_path
        or type(markdown) is not str
        or not markdown.strip()
        or warnings != ()
        or not isinstance(metadata, Mapping)
        or metadata.get("slot_count") != 2
        or metadata.get("settled_slot_count") != 2
        or metadata.get("reused_slot_count") != 0
        or metadata.get("provider_call_count") != 2
        or metadata.get("historical_provider_model_usage") != ()
        or metadata.get("failed_slots") is not None
        or metadata.get("provider_failures") is not None
        or usage is None
        or markdown.count("## OCRLLM image slot ") != 2
        or "OCRLLM_FAILED_IMAGE_SLOT" in markdown
        or not output_path.is_file()
        or output_path.read_bytes() != markdown.encode("utf-8")
        or state_path.exists()
        or page_paths != tuple(path for batch in batches for path in batch)
        or not all(path.is_file() for path in page_paths)
    ):
        _raise_invalid_result()
    return {
        "page_count": len(page_paths),
        "batch_count": len(batches),
        "provider_call_count": usage["calls"],
        "settled_slot_count": 2,
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "published": True,
        "state_retained": False,
        "caller_owned_page_count": len(page_paths),
        "pages_unchanged": True,
    }


def _safe_route_a_usage(
    value: object,
    *,
    model: str,
) -> dict[str, int] | None:
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
        or row.get("model") != model
        or type(calls) is not int
        or calls != 2
        or type(input_tokens) is not int
        or input_tokens < 0
        or type(output_tokens) is not int
        or output_tokens < 0
    ):
        return None
    return {
        "calls": calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def _file_fingerprints(paths: Sequence[Path]) -> tuple[tuple[int, str], ...]:
    return tuple(_file_fingerprint(Path(path)) for path in paths)


def _file_fingerprint(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _build_pdf_from_images(source_paths: tuple[Path, ...], pdf_path: Path) -> None:
    """Build one bounded live fixture without retaining caller image handles."""
    try:
        from PIL import Image
    except (ImportError, OSError) as error:
        raise ConfigError(
            "The Google PDF live gate requires Pillow.",
            code="CONFIG_INVALID",
        ) from error

    pages = []
    try:
        for source_path in source_paths:
            with Image.open(source_path) as source:
                page = source.convert("RGB")
                page.thumbnail((1280, 1280))
            pages.append(page)
        if len(pages) != PDF_PAGE_COUNT:
            raise ConfigError(
                "The Google PDF live fixture has an invalid page count.",
                code="CONFIG_INVALID",
            ) from None
        pages[0].save(
            pdf_path,
            format="PDF",
            save_all=True,
            append_images=pages[1:],
            resolution=144,
        )
    except OCRLLMError:
        raise
    except (MemoryError, OSError, ValueError) as error:
        raise ConfigError(
            "The Google PDF live fixture could not be built.",
            code="CONFIG_INVALID",
        ) from error
    finally:
        for page in pages:
            page.close()


def _safe_pdf_result_summary(
    result: Any,
    *,
    model: str,
    output_directory: Path,
) -> dict[str, object]:
    metadata = getattr(result, "metadata", None)
    output_path = getattr(result, "output_path", None)
    markdown = getattr(result, "markdown", None)
    if not isinstance(metadata, Mapping) or output_path is None:
        _raise_invalid_result()
    output_path = Path(output_path)
    first_marker = "<!-- ocrllm:pdf-pages start=1 end=8 -->"
    second_marker = "<!-- ocrllm:pdf-pages start=9 end=16 -->"
    usage = metadata.get("current_model_token_usage")
    if (
        getattr(result, "source_type", None) != "pdf"
        or getattr(result, "status", None) != "complete"
        or type(markdown) is not str
        or not markdown.strip()
        or markdown.count("<!-- ocrllm:pdf-pages") != 2
        or first_marker not in markdown
        or second_marker not in markdown
        or markdown.index(first_marker) >= markdown.index(second_marker)
        or output_path != output_directory / "input_board.md"
        or not output_path.is_file()
        or metadata.get("provider") != "google"
        or metadata.get("model") != model
        or metadata.get("page_count") != PDF_PAGE_COUNT
        or metadata.get("pdf_group_count") != 2
        or metadata.get("provider_call_count") != 2
        or metadata.get("current_run_provider_call_count") != 2
        or type(usage) is not tuple
        or len(usage) != 1
        or not isinstance(usage[0], Mapping)
        or usage[0].get("model") != model
    ):
        _raise_invalid_result()

    state_directory = output_directory / "input_board"
    state_paths = tuple(state_directory.glob("*.ocrllm-state.json"))
    if (
        len(state_paths) != 2
        or tuple(state_directory.glob("page-*.png"))
        or not all(_is_complete_google_state(path, model) for path in state_paths)
    ):
        _raise_invalid_result()
    input_tokens = usage[0].get("input_tokens")
    output_tokens = usage[0].get("output_tokens")
    for token_count in (input_tokens, output_tokens):
        if token_count is not None and (
            type(token_count) is not int or token_count < 0
        ):
            _raise_invalid_result()
    return {
        "page_count": PDF_PAGE_COUNT,
        "group_count": 2,
        "provider_call_count": 2,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "published": True,
        "checkpoint_count": 2,
        "rendered_pages_retained": 0,
    }


def _is_complete_google_state(state_path: Path, model: str) -> bool:
    try:
        document = json.loads(state_path.read_text(encoding="utf-8"))
        slots = document["slots"]
        result = document["result"]
        return (
            document["state_version"] == "ocrllm.image-resume.v2"
            and result["status"] == "complete"
            and len(slots) == 1
            and slots[0]["slot_id"] == "draft"
            and slots[0]["provider"] == "google"
            and slots[0]["model"] == model
            and slots[0]["provider_calls_attempted"] == 1
        )
    except Exception:
        return False


def _raise_invalid_result() -> None:
    raise ConfigError(
        "The Google PDF live gate returned incomplete or inconsistent evidence.",
        code="CONFIG_INVALID",
    ) from None


def _safe_failure_summary(
    error: OCRLLMError,
    *,
    route: str,
) -> dict[str, object]:
    return {
        "status": "failed",
        "route": route,
        "error": {
            "code": error.code,
            "scope": error.details.get("failure_scope"),
            "provider_calls_attempted": error.details.get(
                "provider_calls_attempted"
            ),
            "settled_pdf_group_count": error.details.get(
                "settled_pdf_group_count"
            ),
            "settled_slot_count": error.details.get("settled_slot_count"),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    try:
        summary = run_google_genai_pdf_smoke(arguments)
    except OCRLLMError as error:
        summary = _safe_failure_summary(
            error,
            route="route_a" if arguments.route_a else "direct",
        )
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
