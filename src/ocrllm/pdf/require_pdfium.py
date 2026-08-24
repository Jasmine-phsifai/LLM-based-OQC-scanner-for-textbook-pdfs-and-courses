"""Load the one tested PDFium binding lazily."""

from __future__ import annotations

from typing import Any

from ..errors import PDFError


MINIMUM_PDFIUM_API = (5, 11, 0)
MAXIMUM_PDFIUM_API = (5, 12, 0)


def require_pdfium() -> Any:
    """Return the tested pypdfium2 module or a typed backend failure."""
    try:
        import pypdfium2 as pdfium
    except (ImportError, OSError) as error:
        raise PDFError(
            "PDF recognition requires the optional 'pdf-vision' extra.",
            code="PDF_BACKEND_UNAVAILABLE",
            details={"extra": "pdf-vision"},
        ) from error

    try:
        api_tag = pdfium.PYPDFIUM_INFO.api_tag
        beta = pdfium.PYPDFIUM_INFO.beta
        document_type = pdfium.PdfDocument
    except (AttributeError, TypeError) as error:
        raise PDFError(
            "The installed PDF backend does not expose the tested API.",
            code="PDF_BACKEND_UNAVAILABLE",
            details={"extra": "pdf-vision"},
        ) from error
    if (
        type(api_tag) is not tuple
        or len(api_tag) != 3
        or any(type(part) is not int for part in api_tag)
        or not MINIMUM_PDFIUM_API <= api_tag < MAXIMUM_PDFIUM_API
        or beta is not None
        or not callable(document_type)
    ):
        raise PDFError(
            "The installed PDF backend version is not supported.",
            code="PDF_BACKEND_UNAVAILABLE",
            details={"extra": "pdf-vision"},
        ) from None
    return pdfium
