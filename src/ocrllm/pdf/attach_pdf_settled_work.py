"""Attach already-settled PDF group work to one typed failure."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..errors import OCRLLMError
from ..result import RecognitionResult


def attach_pdf_settled_work(
    error: OCRLLMError,
    settled_results: Sequence[RecognitionResult],
) -> None:
    """Preserve current-run call and token evidence without changing error type."""
    settled_calls = 0
    usage_by_model: dict[str, dict[str, int | None]] = {}
    for result in settled_results:
        calls = result.metadata.get("current_run_provider_call_count", 0)
        if type(calls) is int and calls >= 0:
            settled_calls += calls
        usage = result.metadata.get("current_model_token_usage", ())
        if type(usage) is tuple:
            _merge_result_usage(usage_by_model, usage)

    local_calls = error.details.get("provider_calls_attempted", 0)
    if type(local_calls) is not int or local_calls < 0:
        local_calls = 0
    error._add_safe_detail("provider_calls_attempted", settled_calls + local_calls)
    error._add_safe_detail("settled_pdf_group_count", len(settled_results))

    existing_usage = error.details.get("settled_model_usage", ())
    if type(existing_usage) is tuple:
        _merge_error_usage(usage_by_model, existing_usage)
    if usage_by_model:
        error._add_safe_detail(
            "settled_model_usage",
            tuple(
                {
                    "model": model,
                    "input_count": counts["input_tokens"],
                    "output_count": counts["output_tokens"],
                    "unit": "tokens",
                }
                for model, counts in usage_by_model.items()
            ),
        )


def _merge_result_usage(
    totals: dict[str, dict[str, int | None]],
    usage: tuple[object, ...],
) -> None:
    for item in usage:
        if isinstance(item, Mapping):
            _merge_one(
                totals,
                item.get("model"),
                item.get("input_tokens"),
                item.get("output_tokens"),
            )


def _merge_error_usage(
    totals: dict[str, dict[str, int | None]],
    usage: tuple[object, ...],
) -> None:
    for item in usage:
        if isinstance(item, Mapping) and item.get("unit") == "tokens":
            _merge_one(
                totals,
                item.get("model"),
                item.get("input_count"),
                item.get("output_count"),
            )


def _merge_one(
    totals: dict[str, dict[str, int | None]],
    model: object,
    input_count: object,
    output_count: object,
) -> None:
    if type(model) is not str or not model:
        return
    if type(input_count) is not int and input_count is not None:
        return
    if type(output_count) is not int and output_count is not None:
        return
    previous = totals.get(model)
    if previous is None:
        totals[model] = {
            "input_tokens": input_count,
            "output_tokens": output_count,
        }
        return
    previous["input_tokens"] = _add_optional(previous["input_tokens"], input_count)
    previous["output_tokens"] = _add_optional(previous["output_tokens"], output_count)


def _add_optional(left: int | None, right: int | None) -> int | None:
    if left is None or right is None:
        return None
    return left + right
