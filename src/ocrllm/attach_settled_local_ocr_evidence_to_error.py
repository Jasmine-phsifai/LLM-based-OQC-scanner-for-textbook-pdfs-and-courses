"""Attach completed local-OCR facts to a later typed failure."""

from __future__ import annotations

from collections.abc import Mapping

from .errors import OCRLLMError


def attach_settled_local_ocr_evidence_to_error(
    error: OCRLLMError,
    metadata: Mapping[str, object],
) -> None:
    """Preserve a small stable proof that local inference already completed."""
    if metadata.get("recognition_mode") != "ocr":
        return

    engine = metadata.get("ocr_engine")
    engine_version = metadata.get("ocr_engine_version")
    image_count = metadata.get("image_count")
    retained_line_count = metadata.get("retained_line_count")
    if (
        type(engine) is not str
        or not engine
        or type(engine_version) is not str
        or not engine_version
        or type(image_count) is not int
        or image_count < 1
        or type(retained_line_count) is not int
        or retained_line_count < 1
    ):
        return

    evidence: tuple[tuple[str, str | int], ...] = (
        ("ocr_engine", engine),
        ("ocr_engine_version", engine_version),
        ("image_count", image_count),
        ("retained_line_count", retained_line_count),
    )
    if any(key in error.details for key, _value in evidence):
        return
    for key, value in evidence:
        error._add_safe_detail(key, value)
