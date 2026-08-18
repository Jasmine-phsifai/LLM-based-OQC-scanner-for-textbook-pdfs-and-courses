"""Lazily load the maintained RapidOCR factory."""

from __future__ import annotations

from collections.abc import Callable

from ..errors import DependencyMissing, OCRBackendError


def load_rapidocr() -> Callable[..., object]:
    """Return the RapidOCR factory without importing it at package import time."""

    try:
        from rapidocr import RapidOCR
    except ImportError:
        raise DependencyMissing(
            "Local OCR requires the optional 'ocr' dependencies.",
            details={
                "extra": "ocr",
                "engine": "rapidocr",
                "required_distribution": "rapidocr>=3.9,<4",
                # The legacy 'rapidocr-onnxruntime' distribution exposes a different
                # module and a different result API; installing it is not enough.
                "incompatible_distribution": "rapidocr-onnxruntime",
            },
        ) from None
    except Exception:
        raise OCRBackendError(
            "The local OCR backend could not be imported.",
            code="OCR_BACKEND_FAILED",
            details={"engine": "rapidocr", "phase": "import"},
        ) from None
    if not callable(RapidOCR):
        raise OCRBackendError(
            "The local OCR backend installation is invalid.",
            code="OCR_BACKEND_FAILED",
            details={"engine": "rapidocr", "phase": "import"},
        ) from None
    return RapidOCR
