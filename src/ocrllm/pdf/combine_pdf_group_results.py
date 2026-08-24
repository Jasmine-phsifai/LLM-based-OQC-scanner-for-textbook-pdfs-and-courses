"""Combine ordered image-group results into one PDF result body."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

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
    usage_by_model: dict[str, dict[str, int | None]] = {}
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
        usage = result.metadata.get("current_model_token_usage", ())
        if type(usage) is tuple:
            for item in usage:
                if not isinstance(item, Mapping):
                    continue
                model = item.get("model")
                input_tokens = item.get("input_tokens")
                output_tokens = item.get("output_tokens")
                if type(model) is not str or not model:
                    continue
                if type(input_tokens) is not int and input_tokens is not None:
                    continue
                if type(output_tokens) is not int and output_tokens is not None:
                    continue
                previous = usage_by_model.get(model)
                if previous is None:
                    usage_by_model[model] = {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                    }
                else:
                    previous["input_tokens"] = _add_optional_counts(
                        previous["input_tokens"], input_tokens
                    )
                    previous["output_tokens"] = _add_optional_counts(
                        previous["output_tokens"], output_tokens
                    )
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
    if usage_by_model:
        metadata["current_model_token_usage"] = tuple(
            {
                "model": model,
                "input_tokens": counts["input_tokens"],
                "output_tokens": counts["output_tokens"],
            }
            for model, counts in usage_by_model.items()
        )
    if len(providers) == len(results) and len(set(providers)) == 1:
        metadata["provider"] = providers[0]
    if len(models) == len(results) and len(set(models)) == 1:
        metadata["model"] = models[0]
    return ProcessorOutput(
        media_type="pdf",
        markdown="\n\n".join(sections) + "\n",
        profile=profile,
        status="complete",
        hotwords=tuple(hotwords),
        warnings=tuple(warnings),
        metadata=metadata,
    )


def _add_optional_counts(left: int | None, right: int | None) -> int | None:
    if left is None or right is None:
        return None
    return left + right
