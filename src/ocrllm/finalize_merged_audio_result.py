"""Publish one merged-audio result after every slice was attempted."""

from __future__ import annotations

from pathlib import Path

from .compose_merged_audio_markdown import compose_merged_audio_markdown
from .errors import AllCandidatesExhausted
from .merged_audio_resume_state import MergedAudioResumeState
from .output.write_markdown_atomically import write_markdown_atomically
from .provider_model_usage import ProviderModelUsage
from .result import RecognitionResult


def finalize_merged_audio_result(
    state: MergedAudioResumeState,
    *,
    output_path: Path,
    state_path: Path,
    current_usage: tuple[ProviderModelUsage, ...],
    historical_usage: tuple[ProviderModelUsage, ...],
    reused_slot_count: int,
    provider_failures: tuple[dict[str, int | str], ...],
    overwrite: bool,
) -> RecognitionResult:
    """Publish complete/partial Markdown or raise when no slice settled."""
    settled_count = sum(slot.status == "settled" for slot in state.slots)
    no_speech_count = sum(
        slot.status == "settled" and slot.no_speech for slot in state.slots
    )
    failed_slots = tuple(
        {
            "slot_index": slot.index,
            "provider": slot.vendor,
            "model": slot.model,
            "code": slot.error_code,
            "description": slot.error_description,
        }
        for slot in state.slots
        if slot.status != "settled"
    )
    current_calls = sum(row.calls for row in current_usage)
    if settled_count == 0:
        raise AllCandidatesExhausted(
            "No provider candidate could settle any merged-audio slot.",
            details={
                "failed_slots": failed_slots,
                "provider_calls_attempted": current_calls,
                "current_provider_model_usage": _usage_documents(current_usage),
            },
        ) from None

    markdown = compose_merged_audio_markdown(state.slots)
    write_markdown_atomically(output_path, markdown, overwrite=overwrite)
    warnings: list[str] = []
    if provider_failures:
        warnings.append(
            "Recognition completed after one or more provider candidates failed."
        )
    if state.provider_cleanup_failed:
        warnings.append(
            "At least one provider audio upload or client could not be cleaned up."
        )
    status = "partial" if failed_slots else "complete"
    if status == "complete":
        try:
            state_path.unlink(missing_ok=True)
        except (OSError, ValueError):
            warnings.append(
                "The completed merged-audio resume state could not be removed."
            )
    metadata: dict[str, object] = {
        "slot_count": len(state.slots),
        "settled_slot_count": settled_count,
        "no_speech_slot_count": no_speech_count,
        "reused_slot_count": reused_slot_count,
        "provider_call_count": current_calls,
        "current_provider_model_usage": _usage_documents(current_usage),
        "historical_provider_model_usage": _usage_documents(historical_usage),
        "duration_seconds": state.slots[-1].logical_end_seconds,
        "byte_size": state.source.byte_size,
    }
    if failed_slots:
        metadata["failed_slots"] = failed_slots
    if provider_failures:
        metadata["provider_failures"] = provider_failures
    return RecognitionResult(
        markdown=markdown,
        source_type="audio",
        status=status,
        output_path=output_path,
        warnings=tuple(warnings),
        metadata=metadata,
    )


def _usage_documents(
    usage: tuple[ProviderModelUsage, ...],
) -> tuple[dict[str, str | int | None], ...]:
    return tuple(
        {
            "vendor": row.vendor,
            "model": row.model,
            "calls": row.calls,
            "input_tokens": row.input_tokens,
            "output_tokens": row.output_tokens,
        }
        for row in usage
    )
