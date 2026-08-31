"""Run one fixed 700-page provider-free Route A extraction stress gate."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
import stat
import sys
import tempfile
import time
from pathlib import Path
from types import ModuleType


PAGE_COUNT = 700
BATCH_SIZE = 8
EXPECTED_FULL_BATCH_COUNT = 87
EXPECTED_FINAL_BATCH_SIZE = 4
EXPECTED_RENDERED_SIZE = (200, 200)


def run_pdf_page_extraction_stress() -> dict[str, object]:
    """Return aggregate evidence from one disposable real-PDFium stress run."""
    ocrllm = _load_checkout_ocrllm()
    if ocrllm is None:
        return _failed_summary("PACKAGE_ORIGIN_MISMATCH")

    started = time.monotonic()
    temporary_root: Path | None = None
    summary: dict[str, object]
    try:
        with tempfile.TemporaryDirectory(prefix="ocrllm-pdf-stress-") as temporary:
            temporary_root = Path(temporary)
            summary = _run_stress_in_root(
                ocrllm,
                temporary_root=temporary_root,
                started=started,
            )
    except ocrllm.OCRLLMError as error:
        summary = _failed_summary(error.code, started=started)
    except Exception:
        summary = _failed_summary("UNEXPECTED_SAFE_FAILURE", started=started)

    temporary_root_cleaned = (
        temporary_root is not None and not os.path.lexists(temporary_root)
    )
    summary["temporary_root_cleaned"] = temporary_root_cleaned
    if not temporary_root_cleaned:
        summary["status"] = "failed"
        summary["code"] = "INVALID_SCENARIO_EVIDENCE"
    return summary


def _run_stress_in_root(
    ocrllm: ModuleType,
    *,
    temporary_root: Path,
    started: float,
) -> dict[str, object]:
    pdf_path = temporary_root / "stress.pdf"
    output_directory = temporary_root / "pages"
    _build_stress_pdf(pdf_path)
    source_before = _file_fingerprint(pdf_path)

    page_paths = ocrllm.extract_pdf_pages(
        pdf_path,
        output_dir=output_directory,
    )
    valid_pngs, output_bytes = _validate_page_outputs(
        page_paths,
        output_directory=output_directory,
    )
    batches = ocrllm.batchify_images(
        tuple(page_paths),
        batch_size=BATCH_SIZE,
    )
    batch_sizes = tuple(len(batch) for batch in batches)
    flattened = tuple(path for batch in batches for path in batch)
    source_unchanged = _file_fingerprint(pdf_path) == source_before
    staging_residue_count = len(
        tuple(temporary_root.glob(".ocrllm-pdf-*.tmp"))
    )
    provider_sdk_loaded = bool(
        {name.split(".")[0] for name in sys.modules} & {"google", "openai"}
    )
    passed = (
        type(page_paths) is tuple
        and len(page_paths) == PAGE_COUNT
        and valid_pngs
        and source_unchanged
        and type(batches) is tuple
        and len(batches) == EXPECTED_FULL_BATCH_COUNT + 1
        and batch_sizes
        == (BATCH_SIZE,) * EXPECTED_FULL_BATCH_COUNT
        + (EXPECTED_FINAL_BATCH_SIZE,)
        and flattened == page_paths
        and staging_residue_count == 0
        and not provider_sdk_loaded
    )
    return {
        "status": "passed" if passed else "failed",
        "code": None if passed else "INVALID_SCENARIO_EVIDENCE",
        "requested_page_count": PAGE_COUNT,
        "extracted_page_count": len(page_paths),
        "full_batch_count": sum(size == BATCH_SIZE for size in batch_sizes),
        "final_batch_size": batch_sizes[-1] if batch_sizes else None,
        "batch_count": len(batches),
        "batch_order_matches_pages": flattened == page_paths,
        "png_files_valid": valid_pngs,
        "rendered_output_bytes": output_bytes,
        "source_bytes": source_before[0],
        "source_sha256": source_before[1],
        "source_unchanged": source_unchanged,
        "staging_residue_count": staging_residue_count,
        "provider_call_count": 0,
        "provider_sdk_loaded": provider_sdk_loaded,
        "elapsed_seconds": time.monotonic() - started,
    }


def _build_stress_pdf(pdf_path: Path) -> None:
    import pypdfium2 as pdfium

    if (
        pdfium.PYPDFIUM_INFO.api_tag != (5, 11, 0)
        or pdfium.PYPDFIUM_INFO.beta is not None
    ):
        raise RuntimeError("the stress gate requires the tested PDFium API")
    with pdfium.PdfDocument.new() as document:
        for _ in range(PAGE_COUNT):
            page = document.new_page(72, 72)
            page.close()
        document.save(pdf_path)


def _validate_page_outputs(
    page_paths: object,
    *,
    output_directory: Path,
) -> tuple[bool, int]:
    if type(page_paths) is not tuple or len(page_paths) != PAGE_COUNT:
        return False, 0

    from PIL import Image

    expected_paths = tuple(
        output_directory / f"page-{page_number:06d}.png"
        for page_number in range(1, PAGE_COUNT + 1)
    )
    if page_paths != expected_paths:
        return False, 0
    try:
        directory_paths = tuple(sorted(output_directory.iterdir()))
    except (OSError, ValueError):
        return False, 0
    if directory_paths != expected_paths:
        return False, 0

    output_bytes = 0
    for path in page_paths:
        try:
            info = path.stat()
            if (
                not stat.S_ISREG(info.st_mode)
                or path.is_symlink()
                or info.st_size <= 0
            ):
                return False, output_bytes
            with Image.open(path) as image:
                image.load()
                if image.format != "PNG" or image.size != EXPECTED_RENDERED_SIZE:
                    return False, output_bytes
            output_bytes += info.st_size
        except (OSError, ValueError):
            return False, output_bytes
    return True, output_bytes


def _file_fingerprint(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _load_checkout_ocrllm() -> ModuleType | None:
    expected = (
        Path(__file__).resolve().parents[1] / "src" / "ocrllm" / "__init__.py"
    )
    try:
        spec = importlib.util.find_spec("ocrllm")
        if spec is None or spec.origin is None:
            return None
        if Path(spec.origin).resolve() != expected:
            return None
        module = importlib.import_module("ocrllm")
        origin = getattr(module, "__file__", None)
        return (
            module
            if type(origin) is str and Path(origin).resolve() == expected
            else None
        )
    except (ImportError, OSError, ValueError):
        return None


def _failed_summary(
    code: str,
    *,
    started: float | None = None,
) -> dict[str, object]:
    return {
        "status": "failed",
        "code": code,
        "requested_page_count": PAGE_COUNT,
        "extracted_page_count": None,
        "full_batch_count": None,
        "final_batch_size": None,
        "batch_count": None,
        "batch_order_matches_pages": False,
        "png_files_valid": False,
        "rendered_output_bytes": None,
        "source_bytes": None,
        "source_sha256": None,
        "source_unchanged": False,
        "staging_residue_count": None,
        "provider_call_count": 0,
        "provider_sdk_loaded": False,
        "elapsed_seconds": (
            time.monotonic() - started if started is not None else None
        ),
    }


def main() -> int:
    summary = run_pdf_page_extraction_stress()
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0 if summary.get("status") == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
