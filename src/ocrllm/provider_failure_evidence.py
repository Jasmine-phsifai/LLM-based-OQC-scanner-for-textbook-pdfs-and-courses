"""Read bounded, secret-safe evidence from one typed provider outcome."""

from __future__ import annotations

from collections.abc import Mapping
import re

from .errors import OCRLLMError, ProviderError


MAX_PROVIDER_FAILURE_DESCRIPTION_CHARS = 512
_SAFE_DETAIL_TEXT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


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
    """Return bounded text while retaining safe provider diagnostics.

    Merged resume slots intentionally have a small, stable schema.  Include the
    provider's safe machine code and request id in the existing description so
    those diagnostics survive checkpointing and resume without adding a second
    state schema.
    """
    description = str(error).strip()
    diagnostics = _diagnostic_suffix(error.details)
    if diagnostics:
        suffix = f" [{diagnostics}]"
        available = MAX_PROVIDER_FAILURE_DESCRIPTION_CHARS - len(suffix)
        if len(description) > available:
            description = description[: max(0, available - 3)] + "..."
        return description + suffix
    if len(description) <= MAX_PROVIDER_FAILURE_DESCRIPTION_CHARS:
        return description
    return description[: MAX_PROVIDER_FAILURE_DESCRIPTION_CHARS - 3] + "..."


def _diagnostic_suffix(details: Mapping[str, object]) -> str:
    values: list[str] = []
    for key in ("provider_code", "request_id"):
        value = details.get(key)
        if type(value) is str and _SAFE_DETAIL_TEXT.fullmatch(value) is not None:
            values.append(f"{key}={value}")
    return " ".join(values)
