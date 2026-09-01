"""Validate provider-neutral transcription text and no-speech control."""

from __future__ import annotations

from ..attach_current_model_token_usage_to_error import (
    attach_current_model_token_usage_to_error,
)
from ..audio.no_speech_sentinel import NO_SPEECH_SENTINEL
from ..errors import NoSpeechDetected, OCRLLMError, ProviderError
from .validate_provider_markdown import validate_provider_markdown


def validate_audio_provider_text(
    text: object,
    *,
    vendor: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> str:
    """Return visible transcript text or one usage-bearing typed control/error."""
    value = text if type(text) is str else ""
    stripped = value.strip()
    folded_sentinel = NO_SPEECH_SENTINEL.casefold()
    current_usage = (
        {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    )
    try:
        if stripped.casefold() == folded_sentinel:
            raise NoSpeechDetected(
                details={"provider": vendor, "model": model}
            ) from None
        if folded_sentinel in value.casefold():
            raise ProviderError(
                "The provider returned an invalid no-speech marker.",
                code="PROVIDER_RESPONSE_INVALID",
                details={
                    "provider": vendor,
                    "model": model,
                    "reason": "invalid_no_speech_marker",
                },
            ) from None
        markdown = validate_provider_markdown(value)
    except OCRLLMError as error:
        if "provider" not in error.details:
            error._add_safe_detail("provider", vendor)
        if "model" not in error.details:
            error._add_safe_detail("model", model)
        attach_current_model_token_usage_to_error(error, current_usage)
        raise
    return markdown
