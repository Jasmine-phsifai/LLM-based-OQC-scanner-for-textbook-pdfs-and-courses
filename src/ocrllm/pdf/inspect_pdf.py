"""Inspect every page of one owned PDF before provider work."""

from __future__ import annotations

import math
from pathlib import Path

from ..errors import PDFError
from .open_pdf_document import open_pdf_document
from .pdfium_lock import PDFIUM_LOCK


def inspect_pdf(snapshot_path: Path) -> tuple[tuple[float, float], ...]:
    """Return finite positive page sizes in source order."""
    with PDFIUM_LOCK:
        with open_pdf_document(snapshot_path) as document:
            try:
                page_count = len(document)
                if page_count <= 0:
                    raise PDFError("The PDF contains no pages.") from None
                page_sizes: list[tuple[float, float]] = []
                for page_index in range(page_count):
                    width, height = document.get_page_size(page_index)
                    if (
                        not isinstance(width, (int, float))
                        or not isinstance(height, (int, float))
                        or not math.isfinite(float(width))
                        or not math.isfinite(float(height))
                        or width <= 0
                        or height <= 0
                    ):
                        raise PDFError(
                            "A PDF page has invalid dimensions.",
                            code="PDF_INVALID",
                            details={"page_number": page_index + 1},
                        ) from None
                    page_sizes.append((float(width), float(height)))
            except PDFError:
                raise
            except Exception as error:
                raise PDFError(
                    "The PDF page table could not be inspected.",
                    code="PDF_INVALID",
                ) from error
    return tuple(page_sizes)
