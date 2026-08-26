"""Attach validated current-run model usage to one typed error."""

from __future__ import annotations

from .aggregate_model_token_usage import aggregate_model_token_usage
from .errors import OCRLLMError


def attach_current_model_token_usage_to_error(
    error: OCRLLMError,
    current_usage: object,
) -> None:
    """Preserve nonempty current usage without replacing settled evidence."""
    if type(current_usage) is not tuple or "settled_model_usage" in error.details:
        return
    normalized_usage = aggregate_model_token_usage(current_usage)
    if not normalized_usage:
        return
    error._add_safe_detail(
        "settled_model_usage",
        tuple(
            {
                "model": item["model"],
                "input_count": item["input_tokens"],
                "output_count": item["output_tokens"],
                "unit": "tokens",
            }
            for item in normalized_usage
        ),
    )
