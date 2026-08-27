"""Combine ordered image-group results into one PDF result body."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from ..aggregate_current_model_token_usage import (
    aggregate_current_model_token_usage,
)
from ..processor_output import ProcessorOutput
from ..result import RecognitionResult


def combine_pdf_group_results(
    results: Sequence[RecognitionResult],
    page_ranges: Sequence[tuple[int, int]],
    *,
    profile: str,
) -> ProcessorOutput:
    """Return ordered range-marked Markdown and current-run usage totals."""
    if not results or len(results) != len(page_ranges):
        raise ValueError("PDF group results and ranges must be nonempty and aligned")

    sections: list[str] = []
    current_run_calls = 0
    warnings: list[str] = []
    hotwords: list[str] = []
    providers: list[str] = []
    models: list[str] = []
    for result, (first_page, last_page) in zip(results, page_ranges, strict=True):
        sections.append(
            f"<!-- ocrllm:pdf-pages start={first_page} end={last_page} -->\n\n"
            f"{result.markdown.strip()}"
        )
        calls = result.metadata.get("current_run_provider_call_count", 0)
        if type(calls) is int and calls >= 0:
            current_run_calls += calls
        warnings.extend(result.warnings)
        hotwords.extend(result.hotwords)
        provider = result.metadata.get("provider")
        model = result.metadata.get("model")
        if type(provider) is str and provider:
            providers.append(provider)
        if type(model) is str and model:
            models.append(model)

    metadata: dict[str, object] = {
        "page_count": page_ranges[-1][1],
        "pdf_group_count": len(results),
        "pages_per_group": 8,
        "provider_call_count": current_run_calls,
        "current_run_provider_call_count": current_run_calls,
    }
    token_usage = aggregate_current_model_token_usage(results)
    if token_usage:
        metadata["current_model_token_usage"] = token_usage
    if len(providers) == len(results) and len(set(providers)) == 1:
        metadata["provider"] = providers[0]
    if len(models) == len(results) and len(set(models)) == 1:
        metadata["model"] = models[0]
    if all(result.metadata.get("recognition_mode") == "ocr" for result in results):
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
        if (
            all(type(engine) is str and engine for engine in engines)
            and len(set(engines)) == 1
            and all(
                type(engine_version) is str and engine_version
                for engine_version in engine_versions
            )
            and len(set(engine_versions)) == 1
            and all(type(count) is int and count > 0 for count in image_counts)
            and all(
                type(count) is int and count > 0 for count in retained_line_counts
            )
            and all(type(count) is int and count == 0 for count in network_call_counts)
        ):
            metadata.update(
                {
                    "recognition_mode": "ocr",
                    "ocr_engine": engines[0],
                    "ocr_engine_version": engine_versions[0],
                    "image_count": sum(cast(tuple[int, ...], image_counts)),
                    "retained_line_count": sum(
                        cast(tuple[int, ...], retained_line_counts)
                    ),
                    "network_call_count": 0,
                }
            )
    return ProcessorOutput(
        media_type="pdf",
        markdown="\n\n".join(sections) + "\n",
        profile=profile,
        status=(
            "partial"
            if any(result.status == "partial" for result in results)
            else "complete"
        ),
        hotwords=tuple(hotwords),
        warnings=tuple(warnings),
        metadata=metadata,
    )
