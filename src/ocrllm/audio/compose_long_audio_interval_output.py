"""Compose ordered settled interval slots into one audio result."""

from __future__ import annotations

from ..errors import NoSpeechDetected
from ..processor_output import ProcessorOutput
from .aggregate_long_audio_cleanup import aggregate_long_audio_cleanup
from .long_audio_settled_slot import LongAudioSettledSlot
from .transcription_prompt import NO_SPEECH_SENTINEL


def compose_long_audio_interval_output(
    snapshot,
    slots: tuple[LongAudioSettledSlot, ...],
    *,
    current_calls: int,
    current_usage: tuple[tuple[int | None, int | None], ...],
) -> ProcessorOutput:
    """Omit settled silence and disclose current versus reused work."""
    spoken_markdown = tuple(
        slot.markdown for slot in slots if slot.markdown != NO_SPEECH_SENTINEL
    )
    remote_file_deleted = aggregate_long_audio_cleanup(
        tuple(slot.provider_file_cleanup_succeeded for slot in slots)
    )
    provider_client_closed = aggregate_long_audio_cleanup(
        tuple(slot.provider_client_cleanup_succeeded for slot in slots)
    )
    if not spoken_markdown:
        raise NoSpeechDetected(
            details={
                "provider": slots[0].provider,
                "model": slots[0].model,
                "provider_calls_attempted": current_calls,
                "remote_file_deleted": remote_file_deleted,
                "provider_client_closed": provider_client_closed,
            }
        ) from None
    current_slot_count = len(current_usage)
    historical_slots = slots[:-current_slot_count] if current_slot_count else slots
    warnings = tuple(warning for slot in slots for warning in slot.warnings)
    model = slots[0].model
    return ProcessorOutput(
        media_type="audio",
        markdown="\n\n".join(spoken_markdown),
        status="complete" if not warnings else "partial",
        warnings=warnings,
        metadata={
            "provider": "google",
            "model": model,
            "transport": "google_files",
            "provider_call_count": sum(
                slot.provider_calls_attempted for slot in slots
            ),
            "current_run_provider_call_count": current_calls,
            "current_model_token_usage": _aggregate_usage(model, current_usage),
            "historical_model_token_usage": _aggregate_usage(
                model,
                tuple(
                    (slot.input_tokens, slot.output_tokens)
                    for slot in historical_slots
                ),
            ),
            "duration_seconds": snapshot.duration_seconds,
            "byte_size": snapshot.byte_size,
            "remote_file_deleted": remote_file_deleted,
            "provider_client_closed": provider_client_closed,
        },
    )


def _aggregate_usage(
    model: str,
    usage: tuple[tuple[int | None, int | None], ...],
) -> tuple[dict[str, object], ...]:
    if not usage:
        return ()
    input_values = tuple(value[0] for value in usage)
    output_values = tuple(value[1] for value in usage)
    return (
        {
            "model": model,
            "input_tokens": (
                sum(input_values)
                if all(value is not None for value in input_values)
                else None
            ),
            "output_tokens": (
                sum(output_values)
                if all(value is not None for value in output_values)
                else None
            ),
        },
    )
