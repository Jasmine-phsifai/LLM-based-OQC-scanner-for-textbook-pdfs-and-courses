"""Build the initial state for one fixed merged-audio plan."""

from __future__ import annotations

from .audio_slice import AudioSlice
from .contracts.source_fingerprint import SourceFingerprint
from .merged_audio_resume_state import (
    MERGED_AUDIO_RESUME_STATE_VERSION,
    MergedAudioResumeState,
    MergedAudioSlot,
)


def build_merged_audio_resume_state(
    slices: tuple[AudioSlice, ...],
    *,
    mode: str,
    interval_minutes: int | None,
    prompt_version: str,
    source: SourceFingerprint,
) -> MergedAudioResumeState:
    """Reserve every explicit audio range before any provider dispatch."""
    return MergedAudioResumeState(
        state_version=MERGED_AUDIO_RESUME_STATE_VERSION,
        mode=mode,
        interval_minutes=interval_minutes,
        prompt_version=prompt_version,
        source=source,
        slots=tuple(
            MergedAudioSlot(
                index=item.index,
                logical_start_seconds=item.logical_start_seconds,
                logical_end_seconds=item.logical_end_seconds,
                actual_start_seconds=item.actual_start_seconds,
                actual_end_seconds=item.actual_end_seconds,
            )
            for item in slices
        ),
    )
