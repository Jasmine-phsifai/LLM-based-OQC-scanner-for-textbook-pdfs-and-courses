"""Validate recognized Markdown loaded from durable audio state."""

from __future__ import annotations

from ..providers.validate_provider_markdown import validate_provider_markdown
from .transcription_prompt import NO_SPEECH_SENTINEL


def validate_saved_audio_markdown(
    value: object,
    *,
    allow_no_speech_sentinel: bool,
) -> None:
    """Reject saved content that a fresh audio response could not settle."""
    if type(value) is not str:
        raise ValueError("saved audio Markdown is invalid") from None

    folded_sentinel = NO_SPEECH_SENTINEL.casefold()
    if value == NO_SPEECH_SENTINEL:
        if allow_no_speech_sentinel:
            return
        raise ValueError("saved audio Markdown misuses the no-speech marker") from None
    if folded_sentinel in value.casefold():
        raise ValueError("saved audio Markdown has an invalid no-speech marker") from None
    validate_provider_markdown(value)
