"""Parse one non-streaming DashScope Chat Completions image response."""

from __future__ import annotations

from ...errors import ProviderError
from ..vision_provider_response import VisionProviderResponse


def parse_dashscope_image_response(
    response: object,
    *,
    model: str,
) -> VisionProviderResponse:
    """Return complete Markdown and optional compatible-endpoint token usage."""
    details = {"provider": "dashscope", "model": model}
    try:
        choices = getattr(response, "choices")
        response_model = getattr(response, "model")
        if type(choices) is not list or len(choices) != 1:
            raise TypeError
        choice = choices[0]
        choice_index = getattr(choice, "index")
        finish_reason = getattr(choice, "finish_reason")
        message = getattr(choice, "message")
        role = getattr(message, "role")
        content = getattr(message, "content")
        refusal = getattr(message, "refusal", None)
    except Exception:
        raise ProviderError(
            "DashScope returned a malformed image-recognition response.",
            code="PROVIDER_RESPONSE_INVALID",
            details=details,
        ) from None

    if type(response_model) is not str or response_model != model:
        raise ProviderError(
            "DashScope reported a different model than the requested model.",
            code="PROVIDER_RESPONSE_INVALID",
            details=details,
        ) from None
    if (
        type(choice_index) is not int
        or choice_index != 0
        or type(role) is not str
        or role != "assistant"
    ):
        raise ProviderError(
            "DashScope returned an invalid assistant choice.",
            code="PROVIDER_RESPONSE_INVALID",
            details=details,
        ) from None
    if type(finish_reason) is str and finish_reason == "length":
        raise ProviderError(
            "DashScope returned a truncated image-recognition response.",
            code="PROVIDER_RESPONSE_INVALID",
            details=details,
        ) from None
    if type(finish_reason) is not str or finish_reason != "stop":
        raise ProviderError(
            "DashScope returned an incomplete image-recognition response.",
            code="PROVIDER_RESPONSE_INVALID",
            details={**details, "reason": "incomplete"},
        ) from None
    if refusal is not None:
        raise ProviderError(
            "DashScope refused the image-recognition request.",
            code="PROVIDER_RESPONSE_INVALID",
            details=details,
        ) from None
    if type(content) is not str:
        raise ProviderError(
            "DashScope returned no text image-recognition content.",
            code="PROVIDER_RESPONSE_INVALID",
            details=details,
        ) from None
    usage = _safe_attribute(response, "usage")
    return VisionProviderResponse(
        markdown=content,
        input_tokens=_optional_token_count(usage, "prompt_tokens"),
        output_tokens=_optional_token_count(usage, "completion_tokens"),
    )


def _optional_token_count(usage: object | None, name: str) -> int | None:
    if usage is None:
        return None
    value = _safe_attribute(usage, name)
    return value if type(value) is int and value >= 0 else None


def _safe_attribute(value: object, name: str) -> object | None:
    try:
        return getattr(value, name, None)
    except Exception:
        return None
