"""Atomically save one completed image result before final publication."""

from __future__ import annotations

# Kept as this module's established fault-injection seam. The shared writer
# imports the same module object, so existing save-lifecycle regressions still
# exercise its replace failures without duplicating the implementation.
import os
from pathlib import Path

from ..errors import OutputError
from ..image_resume_state import ImageResumeState
from ..serialize_image_resume_state import serialize_image_resume_state
from .write_resume_state_atomically import write_resume_state_atomically


_MAX_STATE_BYTES = 16 * 1024 * 1024


def save_image_resume_state_atomically(
    state_path: Path,
    state: ImageResumeState,
) -> None:
    """Durably replace state through a unique sibling temporary file."""
    raw = serialize_image_resume_state(state)
    if len(raw) > _MAX_STATE_BYTES:
        raise OutputError(
            "The completed image result exceeds the resume-state limit.",
            code="OUTPUT_WRITE_FAILED",
        ) from None
    write_resume_state_atomically(
        state_path,
        raw,
        maximum_bytes=_MAX_STATE_BYTES,
    )
