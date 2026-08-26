"""Ordered model-token aggregation without invented usage."""

from ocrllm.aggregate_model_token_usage import aggregate_model_token_usage


def test_aggregate_model_token_usage_preserves_order_and_unknown_counts() -> None:
    assert aggregate_model_token_usage(
        (
            {"model": "model-a", "input_tokens": 10, "output_tokens": None},
            {"model": "model-b", "input_tokens": 3, "output_tokens": 1},
            {"model": "model-a", "input_tokens": 2, "output_tokens": 4},
        )
    ) == (
        {"model": "model-a", "input_tokens": 12, "output_tokens": None},
        {"model": "model-b", "input_tokens": 3, "output_tokens": 1},
    )
