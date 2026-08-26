"""Attach current long-audio slot evidence to an operation error."""

from __future__ import annotations

from ..aggregate_current_model_token_usage import (
    aggregate_current_model_token_usage,
)
from ..aggregate_model_token_usage import aggregate_model_token_usage
from ..errors import OCRLLMError
from .aggregate_long_audio_cleanup import aggregate_long_audio_cleanup
from .long_audio_settled_slot import LongAudioSettledSlot


def attach_long_audio_slots_evidence_to_error(
    error: OCRLLMError,
    slots: tuple[LongAudioSettledSlot, ...],
) -> None:
    """Merge current settled usage and cleanup into one operation error."""
    if not slots:
        return
    usage = aggregate_model_token_usage(
        (
            *tuple(
                {
                    "model": slot.model,
                    "input_tokens": slot.input_tokens,
                    "output_tokens": slot.output_tokens,
                }
                for slot in slots
            ),
            *aggregate_current_model_token_usage((), (error,)),
        )
    )
    if usage:
        error._add_safe_detail(
            "settled_model_usage",
            tuple(
                {
                    "model": item["model"],
                    "input_count": item["input_tokens"],
                    "output_count": item["output_tokens"],
                    "unit": "tokens",
                }
                for item in usage
            ),
        )
    for key, values in (
        (
            "remote_file_deleted",
            tuple(slot.provider_file_cleanup_succeeded for slot in slots),
        ),
        (
            "provider_client_closed",
            tuple(slot.provider_client_cleanup_succeeded for slot in slots),
        ),
    ):
        if key in error.details:
            existing = error.details[key]
            values = (*values, existing if type(existing) is bool else None)
        value = aggregate_long_audio_cleanup(values)
        if type(value) is bool:
            error._add_safe_detail(key, value)
