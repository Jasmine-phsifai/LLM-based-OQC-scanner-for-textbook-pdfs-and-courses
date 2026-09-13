"""Map common OpenAI-client failures without vendor-specific guesses."""

from __future__ import annotations

import re

from ...errors import (
    InvalidSource,
    OCRLLMError,
    ProviderError,
    ProviderPermissionDenied,
    ProviderRequestInvalid,
    ProviderUnavailable,
    RateLimited,
)


_SAFE_PROVIDER_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def map_openai_compatible_error(
    error: Exception,
    *,
    openai_module: object | None,
    vendor: str,
    model: str,
    capture_error_output: bool = False,
) -> OCRLLMError:
    """Return one redacted canonical error from shared SDK/HTTP evidence."""
    status = _safe_integer_attribute(error, "status_code")
    details: dict[str, object] = {"provider": vendor, "model": model}
    if status is not None:
        details["http_status"] = status
    provider_code = _extract_provider_code(error)
    if provider_code is not None:
        details["provider_code"] = provider_code
    request_id = _safe_text_attribute(error, "request_id")
    if request_id is not None:
        details["request_id"] = request_id
    if capture_error_output and provider_code == 'output_token_limit':
        output = _extract_generation_output(error)
        if output is not None:
            details['generation_output'] = output
            usage = output.get('usage', {})
            for name, key in (('input_tokens', 'prompt_tokens'), ('output_tokens', 'completion_tokens')):
                if key in usage:
                    details[name] = usage[key]
                else:
                    direct_key = 'input_tokens' if name == 'input_tokens' else 'generated_tokens'
                    if type(output.get(direct_key)) is int:
                        details[name] = output[direct_key]

    if _is_sdk_error(error, openai_module, "APITimeoutError") or isinstance(
        error, TimeoutError
    ) or status in {408, 504}:
        return ProviderError(
            "The OpenAI-compatible endpoint timed out.",
            code="PROVIDER_TIMEOUT",
            details={**details, "failure_scope": "provider"},
        )
    if (
        _is_sdk_error(error, openai_module, "APIConnectionError")
        or isinstance(error, ConnectionError)
        or status is None
        and isinstance(error, OSError)
    ):
        return ProviderError(
            "The OpenAI-compatible endpoint could not be reached.",
            code="PROVIDER_NETWORK",
            details={**details, "failure_scope": "provider"},
        )
    if _is_sdk_error(error, openai_module, "AuthenticationError") or status == 401:
        return ProviderError(
            "The OpenAI-compatible endpoint rejected the credential.",
            code="PROVIDER_AUTHENTICATION",
            details={**details, "failure_scope": "credential"},
        )
    if _is_sdk_error(error, openai_module, "PermissionDeniedError") or status in {
        402,
        403,
    }:
        return ProviderPermissionDenied(
            "The OpenAI-compatible endpoint denied this workflow.",
            details={**details, "failure_scope": "credential"},
        )
    if _is_sdk_error(error, openai_module, "RateLimitError") or status == 429:
        return RateLimited(
            "The OpenAI-compatible endpoint rate-limited the request.",
            details={**details, "failure_scope": "provider"},
        )
    if (
        _is_sdk_error(error, openai_module, "InternalServerError")
        or status == 409
        or status is not None
        and 500 <= status <= 599
    ):
        return ProviderUnavailable(
            "The OpenAI-compatible endpoint is temporarily unavailable.",
            details={**details, "failure_scope": "provider"},
        )
    if status == 413:
        return InvalidSource(
            "The OpenAI-compatible endpoint rejected an oversized request.",
            code="SOURCE_TOO_LARGE",
            details=details,
        )
    if status == 415:
        return InvalidSource(
            "The OpenAI-compatible endpoint rejected the media type.",
            code="SOURCE_INVALID",
            details=details,
        )
    if status in {400, 404, 422}:
        return ProviderRequestInvalid(
            "The OpenAI-compatible endpoint rejected the model or request.",
            details={**details, "failure_scope": "request"},
        )
    return ProviderError(
        "The OpenAI-compatible endpoint failed without a valid response.",
        code="PROVIDER_RESPONSE_INVALID",
        details={**details, "failure_scope": "request"},
    )


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
    return value if type(value) is int and 100 <= value <= 599 else None


def _safe_text_attribute(error: Exception, name: str) -> str | None:
    try:
        value = getattr(error, name, None)
    except Exception:
        return None
    return (
        value
        if type(value) is str and _SAFE_PROVIDER_VALUE.fullmatch(value) is not None
        else None
    )


def _extract_provider_code(error: Exception) -> str | None:
    direct = _safe_text_attribute(error, "code")
    if direct is not None:
        return direct
    try:
        body = getattr(error, "body", None)
    except Exception:
        return None
    if type(body) is not dict:
        return None
    for candidate in (body.get("code"), _nested_error_code(body.get("error"))):
        if (
            type(candidate) is str
            and _SAFE_PROVIDER_VALUE.fullmatch(candidate) is not None
        ):
            return candidate
    return None


def _nested_error_code(value: object) -> object:
    return value.get("code") if type(value) is dict else None


def _extract_generation_output(error: Exception) -> dict | None:
    """Opt-in output evidence only: never copy generic error bodies or headers."""
    try:
        body = getattr(error, 'body', None)
    except Exception:
        return None
    if type(body) is not dict:
        return None
    body = body.get('error', body)
    if type(body) is not dict or type(body.get('details')) is not dict:
        return None
    value = body['details'].get('generation_output')
    if type(value) is not dict:
        return None
    output = {}
    message = value.get('message')
    if type(message) is dict:
        output['message'] = {k: message[k] for k in ('content', 'reasoning_content', 'reasoning')
                             if k in message and (message[k] is None or type(message[k]) is str)}
    elif message is None:
        output['message'] = None
    for key in ('finish_reason', 'artifact_path', 'artifact_error', 'request_id', 'input_audio_sha256'):
        if type(value.get(key)) is str:
            output[key] = value[key]
    for key in ('artifact_saved', 'reached_eos'):
        if type(value.get(key)) is bool:
            output[key] = value[key]
    for key in ('context_tokens', 'max_output_tokens', 'input_tokens', 'generated_tokens', 'max_new_tokens'):
        if type(value.get(key)) is int and value[key] >= 0:
            output[key] = value[key]
    usage = value.get('usage')
    output['usage'] = ({k: usage[k] for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')
                        if type(usage.get(k)) is int and usage[k] >= 0}
                       if type(usage) is dict else {})
    return output
