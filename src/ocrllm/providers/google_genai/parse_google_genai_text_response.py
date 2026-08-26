"""Extract text and token usage from one Google generateContent response."""

from __future__ import annotations

from ...attach_current_model_token_usage_to_error import (
    attach_current_model_token_usage_to_error,
)
from ...errors import ProviderContentBlocked, ProviderError
from .google_genai_text_response import GoogleGenAITextResponse


def parse_google_genai_text_response(
    response: object,
    *,
    model: str,
) -> GoogleGenAITextResponse:
    """Return exact text and optional provider-reported token counts."""
    text = _safe_attribute(response, "text")
    usage = _safe_attribute(response, "usage_metadata")
    prompt_feedback = _safe_attribute(response, "prompt_feedback")
    candidate_source = _safe_attribute(response, "candidates")
    try:
        candidates = tuple(candidate_source) if candidate_source is not None else ()
    except Exception:
        candidates = ()
    if _prompt_was_blocked(prompt_feedback) or _candidate_was_blocked(candidates):
        raise ProviderContentBlocked(
            "Google GenAI blocked the submitted recognition request.",
            details={
                "provider": "google",
                "model": model,
                "failure_scope": "request",
            },
        ) from None
    if type(text) is not str:
        text = _candidate_text(candidates)
    input_tokens = _optional_token_count(usage, "prompt_token_count")
    output_tokens = _optional_token_count(usage, "candidates_token_count")
    if text is None:
        error = ProviderError(
            "Google GenAI returned no recognition text.",
            code="PROVIDER_RESPONSE_INVALID",
            details={
                "provider": "google",
                "model": model,
                "reason": "missing_text",
            },
        )
        if input_tokens is not None or output_tokens is not None:
            attach_current_model_token_usage_to_error(
                error,
                (
                    {
                        "model": model,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                    },
                ),
            )
        raise error from None
    return GoogleGenAITextResponse(
        text=text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _candidate_text(candidates: object) -> str | None:
    try:
        iterator = iter(candidates)
    except Exception:
        return None
    pieces: list[str] = []
    for candidate in iterator:
        try:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", ())
            for part in parts:
                value = getattr(part, "text", None)
                if type(value) is str:
                    pieces.append(value)
        except Exception:
            return None
    return "".join(pieces) if pieces else None


def _prompt_was_blocked(prompt_feedback: object | None) -> bool:
    if prompt_feedback is None:
        return False
    try:
        reason = getattr(prompt_feedback, "block_reason", None)
    except Exception:
        return False
    return _is_block_reason(reason)


def _candidate_was_blocked(candidates: object) -> bool:
    try:
        iterator = iter(candidates)
    except Exception:
        return False
    for candidate in iterator:
        try:
            reason = getattr(candidate, "finish_reason", None)
        except Exception:
            continue
        if _is_block_reason(reason):
            return True
    return False


def _is_block_reason(value: object) -> bool:
    if value is None:
        return False
    normalized = str(value).casefold()
    return any(marker in normalized for marker in ("safety", "block", "prohibited"))


def _optional_token_count(usage: object | None, name: str) -> int | None:
    if usage is None:
        return None
    try:
        value = getattr(usage, name, None)
    except Exception:
        return None
    return value if type(value) is int and value >= 0 else None


def _safe_attribute(value: object, name: str) -> object | None:
    try:
        return getattr(value, name, None)
    except Exception:
        return None
