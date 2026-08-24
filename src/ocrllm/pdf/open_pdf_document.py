"""Open and close one PDFium document with typed failures."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ..errors import OCRLLMError, PDFError
from .require_pdfium import require_pdfium


@contextmanager
def open_pdf_document(snapshot_path: Path) -> Iterator[object]:
    """Yield one PDFium document and close it without masking primary failures."""
    pdfium = require_pdfium()
    try:
        document = pdfium.PdfDocument(snapshot_path)
    except Exception as error:
        error_code = getattr(error, "err_code", None)
        if error_code == 4:
            raise PDFError(
                "The PDF requires a password, which this release does not accept.",
                code="PDF_PASSWORD_REQUIRED",
            ) from error
        raise PDFError(
            "The PDF is malformed or cannot be opened.",
            code="PDF_INVALID",
        ) from error

    primary_error: BaseException | None = None
    try:
        yield document
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            document.close()
        except Exception:
            if primary_error is None:
                raise PDFError(
                    "The PDF backend could not release the document safely.",
                    code="PDF_INVALID",
                ) from None
            if isinstance(primary_error, OCRLLMError):
                primary_error._add_safe_detail("pdf_document_cleanup_failed", True)
