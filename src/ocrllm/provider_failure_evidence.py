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
    input_tokens = _safe_optional_count(error.details.get("input_tokens"))
    output_tokens = _safe_optional_count(error.details.get("output_tokens"))
    rows = error.details.get("settled_model_usage")
    if input_tokens is None and output_tokens is None and type(rows) is tuple:
        for row in rows:
            if not isinstance(row, Mapping) or row.get("unit") != "tokens":
                continue
            input_tokens = _safe_optional_count(row.get("input_count"))
            output_tokens = _safe_optional_count(row.get("output_count"))
            break
    return calls, input_tokens, output_tokens


def _safe_optional_count(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


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
