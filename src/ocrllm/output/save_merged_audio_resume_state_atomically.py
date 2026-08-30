"""Save one validated merged-audio resume sidecar."""

from __future__ import annotations

from pathlib import Path

from ..merged_audio_resume_state import MergedAudioResumeState
from .load_merged_audio_resume_state import MERGED_AUDIO_RESUME_STATE_MAX_BYTES
from .write_resume_state_atomically import write_resume_state_atomically


def save_merged_audio_resume_state_atomically(
    state_path: Path,
    state: MergedAudioResumeState,
) -> None:
    """Durably replace one merged-audio sidecar."""
    if type(state) is not MergedAudioResumeState:
        raise TypeError("state must be an exact MergedAudioResumeState")
    write_resume_state_atomically(
        state_path,
        state.to_bytes(),
        maximum_bytes=MERGED_AUDIO_RESUME_STATE_MAX_BYTES,
    )
