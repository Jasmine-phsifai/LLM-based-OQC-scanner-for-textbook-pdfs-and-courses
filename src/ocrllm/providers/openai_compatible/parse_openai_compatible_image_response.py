"""Parse one standard non-streaming image Chat Completion."""

from __future__ import annotations

from ...errors import ProviderError
from ..vision_provider_response import VisionProviderResponse


def parse_openai_compatible_image_response(
    response: object,
    *,
    vendor: str,
    model: str,
) -> VisionProviderResponse:
    """Return text and nullable token usage without requiring model echo equality."""
    details = {"provider": vendor, "model": model}
    try:
        choices = getattr(response, "choices")
        if type(choices) is not list or len(choices) != 1:
            raise TypeError
        choice = choices[0]
        choice_index = getattr(choice, "index")
        finish_reason = getattr(choice, "finish_reason")
        message = getattr(choice, "message")
        role = getattr(message, "role")
        content = getattr(message, "content")
        refusal = getattr(message, "refusal", None)
        response_model = getattr(response, "model")
    except Exception:
        raise ProviderError(
            "The OpenAI-compatible endpoint returned a malformed response.",
            code="PROVIDER_RESPONSE_INVALID",
            details={**details, "reason": "malformed"},
        ) from None

    usage = _safe_attribute(response, "usage")
    usage_details = {
        "input_tokens": _optional_token_count(usage, "prompt_tokens"),
        "output_tokens": _optional_token_count(usage, "completion_tokens"),
    }

    if (
        type(choice_index) is not int
        or choice_index != 0
        or role != "assistant"
        or type(response_model) is not str
        or not response_model
    ):
        raise ProviderError(
            "The OpenAI-compatible endpoint returned an invalid assistant choice.",
            code="PROVIDER_RESPONSE_INVALID",
            details={**details, **usage_details, "reason": "invalid_choice"},
        ) from None
    if finish_reason == "length":
        raise ProviderError(
            "The OpenAI-compatible endpoint truncated the recognition response.",
            code="PROVIDER_RESPONSE_INVALID",
            details={**details, **usage_details, "reason": "truncated"},
        ) from None
    if finish_reason != "stop":
        raise ProviderError(
            "The OpenAI-compatible endpoint returned an incomplete response.",
            code="PROVIDER_RESPONSE_INVALID",
            details={**details, **usage_details, "reason": "incomplete"},
        ) from None
    if refusal is not None:
        raise ProviderError(
            "The OpenAI-compatible endpoint refused the recognition request.",
            code="PROVIDER_REFUSED_RECOGNITION",
            details={**details, **usage_details, "reason": "refusal"},
        ) from None
    if type(content) is not str:
        raise ProviderError(
            "The OpenAI-compatible endpoint returned no text content.",
            code="PROVIDER_RESPONSE_INVALID",
            details={**details, **usage_details, "reason": "missing_text"},
        ) from None

    return VisionProviderResponse(
        markdown=content,
        input_tokens=usage_details["input_tokens"],
        output_tokens=usage_details["output_tokens"],
    )


def _optional_token_count(usage: object | None, name: str) -> int | None:
    value = _safe_attribute(usage, name) if usage is not None else None
    return value if type(value) is int and value >= 0 else None


def _safe_attribute(value: object, name: str) -> object | None:
    try:
        return getattr(value, name, None)
    except Exception:
        return None
