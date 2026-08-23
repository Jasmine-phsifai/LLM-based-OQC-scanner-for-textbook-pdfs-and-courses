"""Validate one Google short-audio response without false success."""

from __future__ import annotations

from ...errors import NoSpeechDetected, OCRLLMError, ProviderError
from ..validate_provider_markdown import validate_provider_markdown
from .google_genai_audio_response import GoogleGenAIAudioResponse
from .parse_google_genai_text_response import parse_google_genai_text_response


NO_SPEECH_SENTINEL = "NOSPEECH4OCRLLM"


def parse_google_genai_audio_response(
    response: object,
    *,
    model: str,
) -> GoogleGenAIAudioResponse:
    """Return a transcript or one explicit no-speech/invalid-response failure."""
    parsed = parse_google_genai_text_response(response, model=model)
    stripped = parsed.text.strip()
    folded_sentinel = NO_SPEECH_SENTINEL.casefold()
    if stripped.casefold() == folded_sentinel:
        raise NoSpeechDetected(
            details={"provider": "google", "model": model}
        ) from None
    if folded_sentinel in parsed.text.casefold():
        raise ProviderError(
            "Google GenAI returned an invalid no-speech marker.",
            code="PROVIDER_RESPONSE_INVALID",
            details={"provider": "google", "model": model},
        ) from None
    try:
        markdown = validate_provider_markdown(parsed.text)
    except OCRLLMError as error:
        if "provider" not in error.details:
            error._add_safe_detail("provider", "google")
        if "model" not in error.details:
            error._add_safe_detail("model", model)
        raise
    return GoogleGenAIAudioResponse(
        markdown=markdown,
        input_tokens=parsed.input_tokens,
        output_tokens=parsed.output_tokens,
    )
