"""Parse one OpenAI-compatible audio transcription response."""

from __future__ import annotations

from ..audio_provider_response import AudioProviderResponse
from ..validate_audio_provider_text import validate_audio_provider_text
from .parse_openai_compatible_chat_response import (
    parse_openai_compatible_chat_response,
)


def parse_openai_compatible_audio_response(
    response: object,
    *,
    vendor: str,
    model: str,
) -> AudioProviderResponse:
    """Return one validated transcript and exact-or-unknown usage."""
    parsed = parse_openai_compatible_chat_response(
        response,
        vendor=vendor,
        model=model,
    )
    markdown = validate_audio_provider_text(
        parsed.text,
        vendor=vendor,
        model=model,
        input_tokens=parsed.input_tokens,
        output_tokens=parsed.output_tokens,
    )
    return AudioProviderResponse(
        markdown=markdown,
        input_tokens=parsed.input_tokens,
        output_tokens=parsed.output_tokens,
    )
