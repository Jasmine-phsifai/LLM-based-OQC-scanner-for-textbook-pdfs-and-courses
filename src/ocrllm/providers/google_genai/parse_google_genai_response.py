"""Parse one native Google image generateContent response."""

from __future__ import annotations

from ..vision_provider_response import VisionProviderResponse
from .parse_google_genai_text_response import parse_google_genai_text_response


def parse_google_genai_response(response: object, *, model: str) -> VisionProviderResponse:
    """Return exact image Markdown and optional provider-reported token counts."""
    parsed = parse_google_genai_text_response(response, model=model)
    return VisionProviderResponse(
        markdown=parsed.text,
        input_tokens=parsed.input_tokens,
        output_tokens=parsed.output_tokens,
    )
