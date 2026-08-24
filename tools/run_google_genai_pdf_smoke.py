"""Prove one bounded 16-page Google PDF recognition run."""

from __future__ import annotations

import argparse
import json
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
    list_google_genai_models,
    recognize,
)
from ocrllm.errors import ConfigError, OCRLLMError


PDF_PAGE_COUNT = 16


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

    if temporary_root.exists():
        raise ConfigError(
            "The Google PDF live gate temporary directory was not cleaned up.",
            code="CONFIG_INVALID",
        ) from None
    return {
        "status": "passed",
        "model": arguments.model,
        "catalog_count": len(catalog),
        **safe_result,
    }


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


def _safe_failure_summary(error: OCRLLMError) -> dict[str, object]:
    return {
        "status": "failed",
        "error": {
            "code": error.code,
            "scope": error.details.get("failure_scope"),
            "provider_calls_attempted": error.details.get(
                "provider_calls_attempted"
            ),
            "settled_pdf_group_count": error.details.get(
                "settled_pdf_group_count"
            ),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    try:
        summary = run_google_genai_pdf_smoke(arguments)
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
