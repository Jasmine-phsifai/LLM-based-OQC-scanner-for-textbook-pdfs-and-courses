"""Map injected-provider failures without exposing provider text."""

from __future__ import annotations

from ..errors import (
    Cancelled,
    ConcurrencyLimited,
    OCRLLMError,
    ProviderAccountSuspended,
    ProviderContentBlocked,
    ProviderError,
    ProviderPermissionDenied,
    ProviderRequestInvalid,
    ProviderUnavailable,
    QuotaExhausted,
    RateLimited,
)


def map_injected_provider_error(error: Exception, *, model: str | None) -> OCRLLMError:
    """Return a redacted public error for one injected-provider failure."""
    details = {} if model is None else {"model": model}
    try:
        raw_code = getattr(error, "code", None)
    except Exception:
        raw_code = None
    code = raw_code if type(raw_code) is str else None

    if isinstance(error, Cancelled) or code == "CANCELLED":
        return Cancelled("Recognition was cancelled before a provider result was available.")
    if isinstance(error, QuotaExhausted) or code == "PROVIDER_QUOTA_EXHAUSTED":
        return QuotaExhausted(
            "The configured provider quota is exhausted.",
            details=details,
        )
    if (
        isinstance(error, ProviderPermissionDenied)
        or code == "PROVIDER_PERMISSION_DENIED"
    ):
        return ProviderPermissionDenied(
            "The configured provider denied permission for this workflow.",
            details=details,
        )
    if (
        isinstance(error, ProviderAccountSuspended)
        or code == "PROVIDER_ACCOUNT_SUSPENDED"
    ):
        return ProviderAccountSuspended(
            "The configured provider account is suspended.",
            details=details,
        )
    if isinstance(error, RateLimited) or code == "PROVIDER_RATE_LIMITED":
        return RateLimited(
            "The configured provider temporarily rate-limited the request.",
            details=details,
        )
    if (
        isinstance(error, ConcurrencyLimited)
        or code == "PROVIDER_CONCURRENCY_LIMITED"
    ):
        return ConcurrencyLimited(
            "The configured provider concurrency limit is active.",
            details=details,
        )
    if isinstance(error, TimeoutError) or code == "PROVIDER_TIMEOUT":
        return ProviderError(
            "The configured provider timed out.",
            code="PROVIDER_TIMEOUT",
            retryable=True,
            details=details,
        )
    if isinstance(error, ConnectionError) or code == "PROVIDER_NETWORK":
        return ProviderError(
            "The configured provider could not be reached.",
            code="PROVIDER_NETWORK",
            retryable=True,
            details=details,
        )
    if code == "PROVIDER_AUTHENTICATION":
        return ProviderError(
            "The configured provider rejected authentication.",
            code="PROVIDER_AUTHENTICATION",
            details=details,
        )
    if isinstance(error, ProviderUnavailable) or code == "PROVIDER_UNAVAILABLE":
        return ProviderUnavailable(
            "The configured provider is temporarily unavailable.",
            details=details,
        )
    if (
        isinstance(error, ProviderRequestInvalid)
        or code == "PROVIDER_REQUEST_INVALID"
    ):
        return ProviderRequestInvalid(
            "The configured provider rejected the request parameters.",
            details=details,
        )
    if (
        isinstance(error, ProviderContentBlocked)
        or code == "PROVIDER_CONTENT_BLOCKED"
    ):
        return ProviderContentBlocked(
            "The configured provider blocked the submitted content.",
            details=details,
        )

    return ProviderError(
        "The configured provider failed without a valid recognition response.",
        code="PROVIDER_RESPONSE_INVALID",
        details=details,
    )
