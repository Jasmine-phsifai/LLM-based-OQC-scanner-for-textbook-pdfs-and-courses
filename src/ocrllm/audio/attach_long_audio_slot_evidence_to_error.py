"""Attach one settled long-audio slot to a persistence error."""

from __future__ import annotations

from ..errors import OCRLLMError
from .long_audio_settled_slot import LongAudioSettledSlot


def attach_long_audio_slot_evidence_to_error(
    error: OCRLLMError,
    slot: LongAudioSettledSlot,
) -> None:
    """Preserve validated usage and cleanup facts without replacing details."""
    if "settled_model_usage" not in error.details:
        error._add_safe_detail(
            "settled_model_usage",
            (
                {
                    "model": slot.model,
                    "input_count": slot.input_tokens,
                    "output_count": slot.output_tokens,
                    "unit": "tokens",
                },
            ),
        )
    for key, value in (
        ("remote_file_deleted", slot.provider_file_cleanup_succeeded),
        ("provider_client_closed", slot.provider_client_cleanup_succeeded),
    ):
        if key not in error.details and type(value) is bool:
            error._add_safe_detail(key, value)
