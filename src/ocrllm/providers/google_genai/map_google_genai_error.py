"""Map native Google SDK failures to stable secret-safe errors."""

from __future__ import annotations

from ...errors import (
    OCRLLMError,
    ProviderError,
    ProviderPermissionDenied,
    ProviderRequestInvalid,
    ProviderUnavailable,
    QuotaExhausted,
    RateLimited,
)


def map_google_genai_error(error: object, *, model: str) -> OCRLLMError:
    """Classify one observed Google status without retaining provider text."""
    code = _integer_attribute(error, "code")
    status = _text_attribute(error, "status")
    message = _private_message(error)
    details: dict[str, str | int] = {"provider": "google", "model": model}
    if code is not None:
        details["http_status"] = code
    if status is not None:
        details["provider_status"] = status

    if code == 401 or status == "UNAUTHENTICATED":
        return ProviderError(
            "Google GenAI rejected the credential.",
            code="PROVIDER_AUTHENTICATION",
            details=_scoped(details, "credential"),
        )
    if isinstance(error, TimeoutError) or code in {408, 504} or status == "DEADLINE_EXCEEDED":
        return ProviderError(
            "The Google GenAI request timed out.",
            code="PROVIDER_TIMEOUT",
            details=_scoped(details, "provider"),
        )
    if isinstance(error, ConnectionError):
        return ProviderError(
            "The Google GenAI service could not be reached.",
            code="PROVIDER_NETWORK",
            details=_scoped(details, "provider"),
        )
    if code == 403 or status == "PERMISSION_DENIED":
        return ProviderPermissionDenied(
            "Google GenAI denied permission for this workflow.",
            details=_scoped(details, "credential"),
        )
    if code == 404 or status == "NOT_FOUND":
        return ProviderUnavailable(
            "The selected Google GenAI model is not currently served.",
            details=_scoped(details, "model"),
        )
    if code == 429 or status == "RESOURCE_EXHAUSTED":
        if _looks_like_spent_quota(message):
            return QuotaExhausted(
                "The selected Google GenAI model quota is exhausted.",
                details=_scoped(details, "model"),
            )
        return RateLimited(
            "Google GenAI temporarily rate-limited the request.",
            details=_scoped(details, "provider"),
        )
    if code in {500, 502, 503} or status in {
        "INTERNAL",
        "UNAVAILABLE",
    }:
        return ProviderUnavailable(
            "Google GenAI is temporarily unavailable.",
            details=_scoped(details, "provider"),
        )
    if code == 400 or status == "INVALID_ARGUMENT":
        if _looks_like_invalid_api_key(message):
            return ProviderError(
                "Google GenAI rejected the credential.",
                code="PROVIDER_AUTHENTICATION",
                details=_scoped(details, "credential"),
            )
        if _looks_like_unsupported_modality(message):
            return ProviderUnavailable(
                "The selected Google GenAI model does not serve this modality.",
                details=_scoped(details, "model"),
            )
        return ProviderRequestInvalid(
            "Google GenAI rejected the request parameters.",
            details=_scoped(details, "request"),
        )
    return ProviderError(
        "Google GenAI failed without a valid recognition response.",
        code="PROVIDER_RESPONSE_INVALID",
        details=_scoped(details, "request"),
    )


def _scoped(details: dict[str, str | int], scope: str) -> dict[str, str | int]:
    return {**details, "failure_scope": scope}


def _integer_attribute(error: object, name: str) -> int | None:
    try:
        value = getattr(error, name, None)
    except Exception:
        return None
    return value if type(value) is int and 100 <= value <= 599 else None


def _text_attribute(error: object, name: str) -> str | None:
    try:
        value = getattr(error, name, None)
    except Exception:
        return None
    if type(value) is str and len(value) <= 128 and value.replace("_", "").isalnum():
        return value
    return None


def _private_message(error: object) -> str:
    try:
        value = getattr(error, "message", "")
    except Exception:
        return ""
    return value.casefold() if type(value) is str and len(value) <= 2048 else ""


def _looks_like_spent_quota(message: str) -> bool:
    return "quota" in message and any(
        marker in message for marker in ("exceed", "exhaust", "billing", "plan")
    )


def _looks_like_unsupported_modality(message: str) -> bool:
    return any(
        marker in message
        for marker in (
            "unsupported modality",
            "modality is not enabled",
            "modality not enabled",
            "does not support image",
            "doesn't support image",
            "only supports text",
        )
    )


def _looks_like_invalid_api_key(message: str) -> bool:
    return "api key" in message and any(
        marker in message for marker in ("invalid", "not valid")
    )
