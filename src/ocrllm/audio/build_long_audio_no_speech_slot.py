"""Preserve one paid interval that contains no speech."""

from __future__ import annotations

import hashlib

from ..aggregate_current_model_token_usage import (
    aggregate_current_model_token_usage,
)
from ..errors import NoSpeechDetected
from .long_audio_settled_slot import LongAudioSettledSlot
from .transcription_prompt import NO_SPEECH_SENTINEL


def build_long_audio_no_speech_slot(
    *,
    window_index: int,
    request_fingerprint: str,
    model: str,
    error: NoSpeechDetected,
) -> LongAudioSettledSlot:
    """Turn the typed no-speech outcome into an exact reusable slot."""
    warnings: list[str] = []
    remote_deleted = error.details.get("remote_file_deleted")
    client_closed = error.details.get("provider_client_closed")
    if remote_deleted is False:
        warnings.append(
            "The Google Files upload could not be deleted after recognition."
        )
    if client_closed is False:
        warnings.append(
            "The Google GenAI client could not be closed after recognition."
        )
    usage = aggregate_current_model_token_usage((), (error,))
    model_usage = (
        usage[0]
        if len(usage) == 1 and usage[0].get("model") == model
        else None
    )
    return LongAudioSettledSlot(
        window_index=window_index,
        request_fingerprint=request_fingerprint,
        markdown=NO_SPEECH_SENTINEL,
        markdown_sha256=hashlib.sha256(NO_SPEECH_SENTINEL.encode("utf-8")).hexdigest(),
        provider="google",
        model=model,
        transport="google_files",
        provider_calls_attempted=error.details.get("provider_calls_attempted", 1),
        input_tokens=(None if model_usage is None else model_usage["input_tokens"]),
        output_tokens=(
            None if model_usage is None else model_usage["output_tokens"]
        ),
        status="complete" if not warnings else "partial",
        warnings=tuple(warnings),
        provider_file_cleanup_succeeded=remote_deleted,
        provider_client_cleanup_succeeded=client_closed,
    )
