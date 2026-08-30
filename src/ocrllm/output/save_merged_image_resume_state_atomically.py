"""Save one validated merged-image resume sidecar."""

from __future__ import annotations

from pathlib import Path

from ..merged_image_resume_state import MergedImageResumeState
from .load_merged_image_resume_state import MERGED_IMAGE_RESUME_STATE_MAX_BYTES
from .write_resume_state_atomically import write_resume_state_atomically


def save_merged_image_resume_state_atomically(
    state_path: Path,
    state: MergedImageResumeState,
) -> None:
    """Durably replace one merged-image sidecar."""
    if type(state) is not MergedImageResumeState:
        raise TypeError("state must be an exact MergedImageResumeState")
    write_resume_state_atomically(
        state_path,
        state.to_bytes(),
        maximum_bytes=MERGED_IMAGE_RESUME_STATE_MAX_BYTES,
    )
