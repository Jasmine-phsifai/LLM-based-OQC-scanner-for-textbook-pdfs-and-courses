"""Combine ordered image-group results into one PDF result body."""

from __future__ import annotations

from collections.abc import Sequence

from ..aggregate_current_model_token_usage import (
    aggregate_current_model_token_usage,
)
from ..aggregate_local_ocr_result_evidence import (
    aggregate_local_ocr_result_evidence,
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

    all_local_ocr = all(
        result.metadata.get("recognition_mode") == "ocr" for result in results
    )
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
    if all_local_ocr:
        metadata.update(aggregate_local_ocr_result_evidence(results))
        from ..local_ocr.recognize_images_with_rapidocr import (
            LOCAL_OCR_LIMITATION_WARNING,
        )

        limitation_warning_seen = False
        local_ocr_warnings: list[str] = []
        for warning in warnings:
            if warning == LOCAL_OCR_LIMITATION_WARNING:
                if limitation_warning_seen:
                    continue
                limitation_warning_seen = True
            local_ocr_warnings.append(warning)
        warnings = local_ocr_warnings
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
