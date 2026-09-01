"""Parse one standard non-streaming OpenAI-compatible Chat Completion."""

from __future__ import annotations

from ...errors import ProviderError
from .openai_compatible_chat_response import OpenAICompatibleChatResponse


def parse_openai_compatible_chat_response(
    response: object,
    *,
    vendor: str,
    model: str,
) -> OpenAICompatibleChatResponse:
    """Return one assistant string without requiring model echo equality."""
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
        _raise_invalid(
            "The OpenAI-compatible endpoint returned an invalid assistant choice.",
            details={**details, **usage_details, "reason": "invalid_choice"},
        )
    if finish_reason == "length":
        _raise_invalid(
            "The OpenAI-compatible endpoint truncated the recognition response.",
            details={**details, **usage_details, "reason": "truncated"},
        )
    if finish_reason != "stop":
        _raise_invalid(
            "The OpenAI-compatible endpoint returned an incomplete response.",
            details={**details, **usage_details, "reason": "incomplete"},
        )
    if refusal is not None:
        raise ProviderError(
            "The OpenAI-compatible endpoint refused the recognition request.",
            code="PROVIDER_REFUSED_RECOGNITION",
            details={**details, **usage_details, "reason": "refusal"},
        ) from None
    if type(content) is not str:
        _raise_invalid(
            "The OpenAI-compatible endpoint returned no text content.",
            details={**details, **usage_details, "reason": "missing_text"},
        )
    return OpenAICompatibleChatResponse(
        text=content,
        input_tokens=usage_details["input_tokens"],
        output_tokens=usage_details["output_tokens"],
    )


def _raise_invalid(message: str, *, details: dict[str, object]) -> None:
    raise ProviderError(
        message,
        code="PROVIDER_RESPONSE_INVALID",
        details=details,
    ) from None


def _optional_token_count(usage: object | None, name: str) -> int | None:
    value = _safe_attribute(usage, name) if usage is not None else None
    return value if type(value) is int and value >= 0 else None


def _safe_attribute(value: object, name: str) -> object | None:
    try:
        return getattr(value, name, None)
    except Exception:
        return None
