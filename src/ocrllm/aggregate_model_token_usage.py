"""Aggregate ordered normalized provider token-usage rows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def aggregate_model_token_usage(
    usage_rows: Sequence[object],
) -> tuple[dict[str, str | int | None], ...]:
    """Sum known input and output tokens by first-seen exact model."""
    totals: dict[str, dict[str, int | None]] = {}
    for item in usage_rows:
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
        if (type(input_tokens) is int and input_tokens < 0) or (
            type(output_tokens) is int and output_tokens < 0
        ):
            continue
        previous = totals.get(model)
        if previous is None:
            totals[model] = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
            continue
        previous["input_tokens"] = _add_known_counts(
            previous["input_tokens"], input_tokens
        )
        previous["output_tokens"] = _add_known_counts(
            previous["output_tokens"], output_tokens
        )

    return tuple(
        {
            "model": model,
            "input_tokens": counts["input_tokens"],
            "output_tokens": counts["output_tokens"],
        }
        for model, counts in totals.items()
    )


def _add_known_counts(left: int | None, right: int | None) -> int | None:
    if left is None or right is None:
        return None
    return left + right
