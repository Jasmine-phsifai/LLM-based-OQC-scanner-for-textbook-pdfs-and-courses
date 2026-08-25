"""Reject long audio that alone exhausts a Google model input context."""

from __future__ import annotations

import math

from ...errors import InvalidSource


GOOGLE_AUDIO_INPUT_TOKENS_PER_SECOND = 32


def validate_google_genai_long_mp3_input_limit(
    *,
    duration_seconds: float,
    input_token_limit: int | None,
    model: str,
) -> None:
    """Reject only a mathematically impossible advertised model request."""
    if input_token_limit is None:
        return
    estimated_audio_input_tokens = math.ceil(
        duration_seconds * GOOGLE_AUDIO_INPUT_TOKENS_PER_SECOND
    )
    if estimated_audio_input_tokens < input_token_limit:
        return
    raise InvalidSource(
        "The MP3 source exhausts the selected Google model input context.",
        code="SOURCE_TOO_LARGE",
        details={
            "provider": "google",
            "model": model,
            "decoded_duration_seconds": duration_seconds,
            "maximum_audio_only_duration_seconds": (
                (input_token_limit - 1) / GOOGLE_AUDIO_INPUT_TOKENS_PER_SECOND
            ),
        },
    ) from None
