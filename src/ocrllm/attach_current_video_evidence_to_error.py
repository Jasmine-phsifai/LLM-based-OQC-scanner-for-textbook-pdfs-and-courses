"""Attach complete current-run video evidence to one primary error."""

from __future__ import annotations

from .aggregate_current_model_token_usage import (
    aggregate_current_model_token_usage,
)
from .aggregate_model_token_usage import aggregate_model_token_usage
from .errors import OCRLLMError
from .result import RecognitionResult


VideoEvidence = RecognitionResult | OCRLLMError


def attach_current_video_evidence_to_error(
    primary_error: OCRLLMError,
    *,
    before: tuple[VideoEvidence, ...] = (),
    after: tuple[VideoEvidence, ...] = (),
    primary_provider_calls_attempted: int | None = None,
) -> None:
    """Merge current calls, usage, and any exact failed client cleanup."""
    ordered_evidence = (*before, primary_error, *after)
    call_counts: list[int | None] = []
    usage_rows: list[dict[str, str | int | None]] = []
    client_cleanup_failed = False
    for item in ordered_evidence:
        if isinstance(item, OCRLLMError):
            count = (
                primary_provider_calls_attempted
                if item is primary_error
                and primary_provider_calls_attempted is not None
                else item.details.get("provider_calls_attempted")
            )
            usage_rows.extend(aggregate_current_model_token_usage((), (item,)))
            client_cleanup_failed |= (
                item.details.get("provider_client_closed") is False
            )
        else:
            count = (
                item.metadata["current_run_provider_call_count"]
                if "current_run_provider_call_count" in item.metadata
                else item.metadata.get("provider_call_count")
            )
            usage_rows.extend(aggregate_current_model_token_usage((item,)))
            client_cleanup_failed |= (
                item.metadata.get("provider_client_closed") is False
            )
        call_counts.append(count if type(count) is int and count >= 0 else None)

    if all(count is not None for count in call_counts):
        primary_error._add_safe_detail(
            "provider_calls_attempted",
            sum(count for count in call_counts if count is not None),
        )
    else:
        primary_error._discard_safe_detail("provider_calls_attempted")

    usage = aggregate_model_token_usage(usage_rows)
    if usage:
        primary_error._add_safe_detail(
            "settled_model_usage",
            tuple(
                {
                    "model": item["model"],
                    "input_count": item["input_tokens"],
                    "output_count": item["output_tokens"],
                    "unit": "tokens",
                }
                for item in usage
            ),
        )
    if client_cleanup_failed:
        primary_error._add_safe_detail("provider_client_closed", False)
