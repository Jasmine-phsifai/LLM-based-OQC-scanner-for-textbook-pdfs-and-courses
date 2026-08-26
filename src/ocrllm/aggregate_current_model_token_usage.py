"""Aggregate provider-reported token usage across successful results."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .aggregate_model_token_usage import aggregate_model_token_usage
from .errors import OCRLLMError
from .result import RecognitionResult


def aggregate_current_model_token_usage(
    results: Sequence[RecognitionResult],
    errors: Sequence[OCRLLMError] = (),
) -> tuple[dict[str, str | int | None], ...]:
    """Sum known settled input and output tokens separately for each model."""
    normalized_rows: list[object] = []
    for result in results:
        usage = result.metadata.get("current_model_token_usage", ())
        if type(usage) is not tuple:
            continue
        for item in usage:
            if isinstance(item, Mapping):
                normalized_rows.append(item)

    for error in errors:
        usage = error.details.get("settled_model_usage", ())
        if type(usage) is not tuple:
            continue
        for item in usage:
            if isinstance(item, Mapping) and item.get("unit") == "tokens":
                normalized_rows.append(
                    {
                        "model": item.get("model"),
                        "input_tokens": item.get("input_count"),
                        "output_tokens": item.get("output_count"),
                    }
                )
    return aggregate_model_token_usage(normalized_rows)
