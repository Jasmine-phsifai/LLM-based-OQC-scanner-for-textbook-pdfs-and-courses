"""Exact current-call aggregation across independent video branches."""

from ocrllm.attach_current_video_evidence_to_error import (
    attach_current_video_evidence_to_error,
)
from ocrllm.errors import OutputError, ProviderUnavailable


def test_unknown_secondary_call_count_removes_primary_subtotal() -> None:
    primary = ProviderUnavailable(
        details={"provider_calls_attempted": 7},
    )
    secondary = OutputError(
        "The independent audio branch failed before its call count was known.",
        code="OUTPUT_WRITE_FAILED",
    )

    attach_current_video_evidence_to_error(
        primary,
        after=(secondary,),
    )

    assert "provider_calls_attempted" not in primary.details
