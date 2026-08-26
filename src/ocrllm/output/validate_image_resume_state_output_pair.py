"""Validate one image resume state against its Markdown target."""

from __future__ import annotations

from pathlib import Path

from ..errors import ResumeStateError
from ..image_resume_state import ImageResumeState


def validate_image_resume_state_output_pair(
    resume_state: ImageResumeState | None,
    output_path: Path,
) -> None:
    """Reject impossible persisted state/output combinations."""
    if not output_path.exists():
        return
    if resume_state is None:
        raise ResumeStateError(
            "Existing image output has no matching resume state.",
            code="RESUME_STATE_INVALID",
        ) from None
    if not resume_state.markdown:
        raise ResumeStateError(
            "Existing image output conflicts with a partial resume state.",
            code="RESUME_STATE_MISMATCH",
        ) from None
