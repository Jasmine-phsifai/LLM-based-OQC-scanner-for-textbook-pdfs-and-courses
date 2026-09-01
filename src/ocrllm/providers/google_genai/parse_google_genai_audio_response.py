"""Validate one Google audio transcript response without false success."""

from __future__ import annotations

from ..validate_audio_provider_text import validate_audio_provider_text
from .google_genai_audio_response import GoogleGenAIAudioResponse
from .parse_google_genai_text_response import parse_google_genai_text_response


def parse_google_genai_audio_response(
    response: object,
    *,
    model: str,
) -> GoogleGenAIAudioResponse:
    """Return a transcript or one explicit no-speech/invalid-response failure."""
    parsed = parse_google_genai_text_response(response, model=model)
    markdown = validate_audio_provider_text(
        parsed.text,
        vendor="google",
        model=model,
        input_tokens=parsed.input_tokens,
        output_tokens=parsed.output_tokens,
    )
    return GoogleGenAIAudioResponse(
        markdown=markdown,
        input_tokens=parsed.input_tokens,
        output_tokens=parsed.output_tokens,
    )
