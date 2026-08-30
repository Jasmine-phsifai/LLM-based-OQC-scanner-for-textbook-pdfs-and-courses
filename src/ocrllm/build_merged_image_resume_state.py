"""Build the initial state for one fixed merged-image plan."""

from __future__ import annotations

from .contracts.source_fingerprint import SourceFingerprint
from .merged_image_resume_state import (
    MERGED_IMAGE_RESUME_STATE_VERSION,
    MergedImageResumeState,
    MergedImageSlot,
)


def build_merged_image_resume_state(
    batches: tuple[tuple[object, ...], ...],
    *,
    image_task: str,
    prompt_version: str,
    sources: tuple[SourceFingerprint, ...],
) -> MergedImageResumeState:
    """Reserve every ordered slot before any provider dispatch."""
    slots: list[MergedImageSlot] = []
    source_index = 0
    for slot_index, batch in enumerate(batches):
        source_indexes = tuple(range(source_index, source_index + len(batch)))
        slots.append(
            MergedImageSlot(index=slot_index, source_indexes=source_indexes)
        )
        source_index += len(batch)
    return MergedImageResumeState(
        state_version=MERGED_IMAGE_RESUME_STATE_VERSION,
        image_task=image_task,
        prompt_version=prompt_version,
        sources=sources,
        slots=tuple(slots),
    )
