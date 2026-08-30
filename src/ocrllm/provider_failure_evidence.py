"""Read bounded, secret-safe evidence from one typed provider outcome."""

from __future__ import annotations

from collections.abc import Mapping

from .errors import OCRLLMError, ProviderError


MAX_PROVIDER_FAILURE_DESCRIPTION_CHARS = 512


def provider_failure_usage(
    error: OCRLLMError,
) -> tuple[int, int | None, int | None]:
    """Return exact calls and trustworthy token dimensions from one error."""
    calls = error.details.get("provider_calls_attempted")
    if type(calls) is not int or calls < 0:
        calls = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    rows = error.details.get("settled_model_usage")
    if type(rows) is tuple:
        for row in rows:
            if not isinstance(row, Mapping) or row.get("unit") != "tokens":
                continue
            candidate_input = row.get("input_count")
            candidate_output = row.get("output_count")
            input_tokens = candidate_input if type(candidate_input) is int else None
            output_tokens = candidate_output if type(candidate_output) is int else None
            break
    return calls, input_tokens, output_tokens


def provider_cleanup_failed(error: OCRLLMError) -> bool:
    """Report any known local or remote provider cleanup failure."""
    return bool(
        error.details.get("provider_file_cleanup_failed") is True
        or error.details.get("remote_file_deleted") is False
        or error.details.get("provider_client_cleanup_failed") is True
        or error.details.get("provider_client_closed") is False
    )


def bounded_provider_failure_description(error: ProviderError) -> str:
    """Return one bounded public description without raw provider details."""
    description = str(error).strip()
    if len(description) <= MAX_PROVIDER_FAILURE_DESCRIPTION_CHARS:
        return description
    return description[: MAX_PROVIDER_FAILURE_DESCRIPTION_CHARS - 3] + "..."
