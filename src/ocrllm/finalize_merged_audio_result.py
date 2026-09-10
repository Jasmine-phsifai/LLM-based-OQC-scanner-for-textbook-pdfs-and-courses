"""Publish one merged-audio result after every slice was attempted."""

from __future__ import annotations

from .observe_recognition import observed_stage

from pathlib import Path
from dataclasses import replace

from .audio_gap_summary import audio_gap_summary
from .output.save_merged_audio_resume_state_atomically import save_merged_audio_resume_state_atomically

from .compose_merged_audio_markdown import compose_merged_audio_markdown
from .errors import AllCandidatesExhausted
from .merged_audio_resume_state import MergedAudioResumeState
from .output.write_markdown_atomically import write_markdown_atomically
from .provider_model_usage import (
    ProviderModelUsage,
    provider_model_usage_documents,
)
from .result import RecognitionResult


@observed_stage('markdown', 'asr')
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
    if settled_count == 0 and not any(
        child.status == 'settled' for parent in state.slots for child in parent.subslots
    ):
        raise AllCandidatesExhausted(
            "No provider candidate could settle any merged-audio slot.",
            details={
                "failed_slots": failed_slots,
                "provider_calls_attempted": current_calls,
                "current_provider_model_usage": provider_model_usage_documents(
                    current_usage
                ),
            },
        ) from None

    gap = audio_gap_summary(state)
    status = ('complete_with_gaps' if gap['accepted_with_gaps']
              else 'partial' if failed_slots else 'complete')
    markdown = compose_merged_audio_markdown(state.slots)
    if status == 'complete_with_gaps':
        markdown = (f"音频识别已完成，但保留明确缺口：{gap['failed_seconds']:.3f} 秒"
                    f"（{gap['failed_fraction']:.2%}）。FAIL 区间未获得可靠转写。\n\n" + markdown)
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
    if status == 'complete_with_gaps':
        state = replace(state, accepted_with_gaps=True)
        save_merged_audio_resume_state_atomically(state_path, state)
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
        "current_provider_model_usage": provider_model_usage_documents(current_usage),
        "historical_provider_model_usage": provider_model_usage_documents(
            historical_usage
        ),
        "duration_seconds": state.slots[-1].logical_end_seconds,
        "byte_size": state.source.byte_size,
    }
    metadata.update(gap)
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
