"""Aggregate stable local-OCR evidence from settled image results."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from .result import RecognitionResult


def aggregate_local_ocr_result_evidence(
    results: Sequence[RecognitionResult],
) -> dict[str, object]:
    """Return uniform engine facts and summed counts, or no evidence."""
    if not results or not all(
        result.metadata.get("recognition_mode") == "ocr" for result in results
    ):
        return {}

    engines = tuple(result.metadata.get("ocr_engine") for result in results)
    engine_versions = tuple(
        result.metadata.get("ocr_engine_version") for result in results
    )
    image_counts = tuple(result.metadata.get("image_count") for result in results)
    retained_line_counts = tuple(
        result.metadata.get("retained_line_count") for result in results
    )
    network_call_counts = tuple(
        result.metadata.get("network_call_count") for result in results
    )
    if not (
        all(type(engine) is str and engine for engine in engines)
        and len(set(engines)) == 1
        and all(
            type(engine_version) is str and engine_version
            for engine_version in engine_versions
        )
        and len(set(engine_versions)) == 1
        and all(type(count) is int and count > 0 for count in image_counts)
        and all(type(count) is int and count > 0 for count in retained_line_counts)
        and all(type(count) is int and count == 0 for count in network_call_counts)
    ):
        return {}

    return {
        "recognition_mode": "ocr",
        "ocr_engine": engines[0],
        "ocr_engine_version": engine_versions[0],
        "image_count": sum(cast(tuple[int, ...], image_counts)),
        "retained_line_count": sum(cast(tuple[int, ...], retained_line_counts)),
        "network_call_count": 0,
    }
