"""Map DashScope/OpenAI failures into stable secret-safe public errors."""

from __future__ import annotations

import re

from ...errors import (
    ConcurrencyLimited,
    InvalidSource,
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


_SAFE_PROVIDER_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_NONRETRYABLE_QUOTA_CODES = frozenset(
    {
        "allocationquotafreetieronly",
        "commoditynotpurchased",
        "freequotaexceeded",
    }
)
_ACCOUNT_SUSPENDED_CODES = frozenset(
    {
        "accountsuspended",
        "arrearage",
        "postpaidbilloverdue",
        "prepaidbilloverdue",
    }
)
_AUTHENTICATION_CODES = frozenset(
    {
        "authenticationerror",
        "invalidaccesstoken",
        "invalidaccesstokenortokenexpired",
        "invalidapikey",
    }
)
_PERMISSION_CODES = frozenset(
    {
        "accessdenied",
        "accessdeniedunpurchased",
        "appaccessdenied",
        "endpointaccessdenied",
        "modelaccessdenied",
        "notauthorized",
        "workspaceaccessdenied",
    }
)
_TIMEOUT_CODES = frozenset(
    {
        "internalerrortimeout",
        "requesttimeout",
        "responsetimeout",
    }
)


def map_dashscope_error(
    error: Exception,
    *,
    openai_module: object,
    model: str,
) -> OCRLLMError:
    """Classify one trusted-adapter failure without exposing provider text."""
    status = _safe_integer_attribute(error, "status_code")
    provider_code = _extract_provider_code(error)
    details: dict[str, str | int] = {
        "provider": "dashscope",
        "model": model,
    }
    if status is not None:
        details["http_status"] = status
    if provider_code is not None:
        details["provider_code"] = provider_code
    request_id = _safe_text_attribute(error, "request_id")
    if request_id is not None:
        details["request_id"] = request_id

    normalized_code = _normalize_provider_code(provider_code)
    private_message = _extract_private_provider_message(error)

    if _is_account_suspended_code(normalized_code):
        return ProviderAccountSuspended(
            "The DashScope account cannot run requests until its account state is restored.",
            details=_scoped(details, "account"),
        )
    if _is_nonretryable_quota_code(normalized_code):
        # Free-tier and unpurchased-commodity quota are granted per model, so
        # one model's exhaustion must not block other candidate models on the
        # same account (audit finding G3). Genuine account-wide states are the
        # suspension codes above, which stay account-scoped.
        return QuotaExhausted(
            "The requested DashScope model has no remaining free quota.",
            details=_scoped(details, "model"),
        )
    if normalized_code == "datainspectionfailed":
        return ProviderContentBlocked(
            "DashScope blocked the submitted content during data inspection.",
            details=_scoped(details, "request"),
        )
    if normalized_code in _TIMEOUT_CODES:
        return ProviderError(
            "The DashScope request timed out.",
            code="PROVIDER_TIMEOUT",
            details=_scoped(details, "provider"),
        )
    if _is_concurrency_failure(normalized_code, private_message):
        return ConcurrencyLimited(
            "DashScope temporarily rejected excess concurrent work.",
            details=_scoped(details, "account", limit_kind="concurrency"),
        )
    if _is_rate_limit_code(normalized_code):
        return RateLimited(
            "DashScope temporarily rate-limited the request.",
            details=_scoped(details, "account", limit_kind="rate"),
        )
    if normalized_code in _AUTHENTICATION_CODES:
        return ProviderError(
            "DashScope rejected the credential.",
            code="PROVIDER_AUTHENTICATION",
            details=_scoped(details, "credential"),
        )
    if _is_permission_code(normalized_code):
        return ProviderPermissionDenied(
            "DashScope denied permission for the configured workflow.",
            details=_scoped(details, _permission_scope(normalized_code)),
        )

    if _is_sdk_error(error, openai_module, "APITimeoutError") or isinstance(
        error, TimeoutError
    ) or status == 408:
        return ProviderError(
            "The DashScope request timed out.",
            code="PROVIDER_TIMEOUT",
            details=_scoped(details, "provider"),
        )
    if _is_sdk_error(error, openai_module, "APIConnectionError") or isinstance(
        error, ConnectionError
    ):
        return ProviderError(
            "The DashScope service could not be reached.",
            code="PROVIDER_NETWORK",
            details=_scoped(details, "provider"),
        )
    if _is_sdk_error(error, openai_module, "AuthenticationError") or status == 401:
        return ProviderError(
            "DashScope rejected the credential.",
            code="PROVIDER_AUTHENTICATION",
            details=_scoped(details, "credential"),
        )
    if _is_sdk_error(error, openai_module, "PermissionDeniedError") or status == 403:
        return ProviderPermissionDenied(
            "DashScope denied permission for the configured workflow.",
            details=_scoped(details, "credential"),
        )
    if _is_sdk_error(error, openai_module, "RateLimitError") or status == 429:
        return RateLimited(
            "DashScope temporarily rate-limited the request.",
            details=_scoped(details, "account", limit_kind="rate"),
        )
    if (
        _is_sdk_error(error, openai_module, "InternalServerError")
        or status == 409
        or status is not None
        and 500 <= status <= 599
    ):
        return ProviderUnavailable(
            "The DashScope model service is temporarily unavailable.",
            details=_scoped(details, "provider"),
        )
    if status == 413:
        return InvalidSource(
            "DashScope rejected the encoded image request as too large.",
            code="SOURCE_TOO_LARGE",
            details=details,
        )
    if status == 415:
        return InvalidSource(
            "DashScope rejected the encoded image media type.",
            code="SOURCE_INVALID",
            details=details,
        )
    if status in {400, 404, 422}:
        return ProviderRequestInvalid(
            "DashScope rejected the configured model, endpoint, or request parameters.",
            details=_scoped(details, "request"),
        )

    return ProviderError(
        "DashScope failed without a valid recognition response.",
        code="PROVIDER_RESPONSE_INVALID",
        details=_scoped(details, "request"),
    )


def _scoped(
    details: dict[str, str | int],
    failure_scope: str,
    *,
    limit_kind: str | None = None,
) -> dict[str, str | int]:
    scoped = {**details, "failure_scope": failure_scope}
    if limit_kind is not None:
        scoped["limit_kind"] = limit_kind
    return scoped


def _is_sdk_error(error: Exception, module: object, class_name: str) -> bool:
    try:
        error_type = getattr(module, class_name, None)
    except Exception:
        return False
    return isinstance(error_type, type) and isinstance(error, error_type)


def _safe_integer_attribute(error: Exception, name: str) -> int | None:
    try:
        value = getattr(error, name, None)
    except Exception:
        return None
    if type(value) is int and 100 <= value <= 599:
        return value
    return None


def _safe_text_attribute(error: Exception, name: str) -> str | None:
    try:
        value = getattr(error, name, None)
    except Exception:
        return None
    if type(value) is str and _SAFE_PROVIDER_VALUE.fullmatch(value) is not None:
        return value
    return None


def _extract_provider_code(error: Exception) -> str | None:
    direct = _safe_text_attribute(error, "code")
    if direct is not None:
        return direct
    body = _safe_exact_dict_attribute(error, "body")
    if body is None:
        return None

    value = body.get("code")
    if type(value) is str and _SAFE_PROVIDER_VALUE.fullmatch(value) is not None:
        return value
    nested = body.get("error")
    if type(nested) is dict:
        value = nested.get("code")
        if type(value) is str and _SAFE_PROVIDER_VALUE.fullmatch(value) is not None:
            return value
    return None


def _extract_private_provider_message(error: Exception) -> str | None:
    direct = _bounded_private_text_attribute(error, "message")
    if direct is not None:
        return direct
    body = _safe_exact_dict_attribute(error, "body")
    if body is None:
        return None
    message = body.get("message")
    if type(message) is str and len(message) <= 1024:
        return message
    nested = body.get("error")
    if type(nested) is dict:
        message = nested.get("message")
        if type(message) is str and len(message) <= 1024:
            return message
    return None


def _safe_exact_dict_attribute(error: Exception, name: str) -> dict | None:
    try:
        value = getattr(error, name, None)
    except Exception:
        return None
    return value if type(value) is dict else None


def _bounded_private_text_attribute(error: Exception, name: str) -> str | None:
    try:
        value = getattr(error, name, None)
    except Exception:
        return None
    if type(value) is str and len(value) <= 1024:
        return value
    return None


def _normalize_provider_code(value: str | None) -> str | None:
    if value is None:
        return None
    return "".join(character for character in value.casefold() if character.isalnum())


def _is_account_suspended_code(value: str | None) -> bool:
    if value is None:
        return False
    return (
        value in _ACCOUNT_SUSPENDED_CODES
        or "billoverdue" in value
        or "accountsuspend" in value
        or "accountnotingoodstanding" in value
    )


def _is_nonretryable_quota_code(value: str | None) -> bool:
    if value is None:
        return False
    return (
        value in _NONRETRYABLE_QUOTA_CODES
        or "commoditynotpurchased" in value
        or "free" in value
        and "quota" in value
        and ("exceed" in value or "expire" in value or "tieronly" in value)
    )


def _is_permission_code(value: str | None) -> bool:
    if value is None:
        return False
    return value in _PERMISSION_CODES or value.endswith("accessdenied")


def _permission_scope(value: str | None) -> str:
    if value == "accessdeniedunpurchased":
        return "account"
    if value in {"endpointaccessdenied", "modelaccessdenied"}:
        return "model"
    return "credential"


def _is_concurrency_failure(value: str | None, private_message: str | None) -> bool:
    if value is not None and ("concurr" in value or "limitconcurrent" in value):
        return True
    if private_message is None:
        return False
    normalized_message = private_message.casefold()
    return "concurr" in normalized_message and any(
        marker in normalized_message
        for marker in ("exceed", "limit", "quota", "too many")
    )


def _is_rate_limit_code(value: str | None) -> bool:
    if value is None:
        return False
    return any(
        marker in value
        for marker in (
            "throttling",
            "ratelimit",
            "limitrequests",
            "limitburstrate",
            "insufficientquota",
        )
    )
