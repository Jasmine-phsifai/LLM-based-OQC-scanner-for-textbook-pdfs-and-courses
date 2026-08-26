"""Validate saved video-audio request facts before resumed media work."""

from __future__ import annotations

from .config import Config
from .errors import ResumeStateError
from .video_job_state import VideoJobState


def validate_video_job_resume_request(
    state: VideoJobState,
    *,
    audio_config: Config,
    audio_interval_minutes: int | None,
) -> None:
    """Reject a changed audio model or interval using journal-only facts."""
    if (
        state.audio.model != audio_config.audio_model.name
        or state.audio.interval_minutes != audio_interval_minutes
    ):
        raise ResumeStateError(
            "The video audio request no longer matches the journal.",
            code="RESUME_STATE_MISMATCH",
        ) from None
