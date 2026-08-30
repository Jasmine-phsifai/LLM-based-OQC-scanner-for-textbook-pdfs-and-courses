"""Atomically save one validated long-audio partial state."""

from __future__ import annotations

# Kept as this module's established fault-injection seam. The shared writer
# imports the same module objects, so existing lifecycle regressions continue
# to exercise replace and deferred-cleanup failures.
import atexit
import os
from pathlib import Path

from ..errors import OutputError
from ..output.write_resume_state_atomically import write_resume_state_atomically
from .long_audio_partial_state import LongAudioPartialState
from .long_audio_partial_state_file_limit import (
    LONG_AUDIO_PARTIAL_STATE_MAX_BYTES,
)
from .serialize_long_audio_partial_state import serialize_long_audio_partial_state


_MAX_STATE_BYTES = LONG_AUDIO_PARTIAL_STATE_MAX_BYTES


def save_long_audio_partial_state_atomically(
    state_path: Path,
    state: LongAudioPartialState,
) -> None:
    """Durably replace an explicit path through one unique sibling file."""
    raw = serialize_long_audio_partial_state(state)
    if len(raw) > _MAX_STATE_BYTES:
        raise OutputError(
            "The long-audio partial state exceeds the safety limit.",
            code="OUTPUT_WRITE_FAILED",
        ) from None
    write_resume_state_atomically(
        state_path,
        raw,
        maximum_bytes=_MAX_STATE_BYTES,
    )
