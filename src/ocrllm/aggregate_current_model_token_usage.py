"""Aggregate provider-reported token usage across successful results."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .errors import OCRLLMError
from .result import RecognitionResult


def aggregate_current_model_token_usage(
    results: Sequence[RecognitionResult],
    errors: Sequence[OCRLLMError] = (),
) -> tuple[dict[str, str | int | None], ...]:
    """Sum known settled input and output tokens separately for each model."""
    totals: dict[str, dict[str, int | None]] = {}
    for result in results:
        usage = result.metadata.get("current_model_token_usage", ())
        if type(usage) is not tuple:
            continue
        for item in usage:
            if isinstance(item, Mapping):
                _merge_one(
                    totals,
                    model=item.get("model"),
                    input_tokens=item.get("input_tokens"),
                    output_tokens=item.get("output_tokens"),
                )

    for error in errors:
        usage = error.details.get("settled_model_usage", ())
        if type(usage) is not tuple:
            continue
        for item in usage:
            if isinstance(item, Mapping) and item.get("unit") == "tokens":
                _merge_one(
                    totals,
                    model=item.get("model"),
                    input_tokens=item.get("input_count"),
                    output_tokens=item.get("output_count"),
                )

    return tuple(
        {
            "model": model,
            "input_tokens": counts["input_tokens"],
            "output_tokens": counts["output_tokens"],
        }
        for model, counts in totals.items()
    )


def _merge_one(
    totals: dict[str, dict[str, int | None]],
    *,
    model: object,
    input_tokens: object,
    output_tokens: object,
) -> None:
    if type(model) is not str or not model:
        return
    if type(input_tokens) is not int and input_tokens is not None:
        return
    if type(output_tokens) is not int and output_tokens is not None:
        return
    previous = totals.get(model)
    if previous is None:
        totals[model] = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        return
    previous["input_tokens"] = _add_known_counts(
        previous["input_tokens"], input_tokens
    )
    previous["output_tokens"] = _add_known_counts(
        previous["output_tokens"], output_tokens
    )


def _add_known_counts(left: int | None, right: int | None) -> int | None:
    if left is None or right is None:
        return None
    return left + right
