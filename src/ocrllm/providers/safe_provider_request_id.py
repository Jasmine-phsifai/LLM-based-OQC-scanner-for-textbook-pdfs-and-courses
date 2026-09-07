"""Validate the small safe request-ID diagnostic carried by provider responses."""

from __future__ import annotations

from ..provider_failure_evidence import _SAFE_DETAIL_TEXT


def safe_provider_request_id(value: object) -> str | None:
    """Return one bounded ASCII request ID, or discard unsafe/missing input."""
    if type(value) is str and _SAFE_DETAIL_TEXT.fullmatch(value) is not None:
        return value
    return None
