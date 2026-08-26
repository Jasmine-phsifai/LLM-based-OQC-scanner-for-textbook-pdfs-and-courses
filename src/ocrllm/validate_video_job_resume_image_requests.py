"""Validate saved video image requests before resumed media work."""

from __future__ import annotations

from .config import Config
from .errors import ResumeStateError
from .fingerprint_image_request import fingerprint_image_request
from .profiles.resolve_image_profile import resolve_image_profile
from .video_job_state import VideoJobState


def validate_video_job_resume_image_requests(
    state: VideoJobState,
    *,
    image_config: Config,
) -> None:
    """Reject changed image-request settings using journaled frame facts."""
    profile = resolve_image_profile(image_config.profile)
    for group in state.frame_groups:
        current_identity = fingerprint_image_request(
            group.identity.sources,
            profile=profile,
            config=image_config,
        )
        if current_identity != group.identity:
            raise ResumeStateError(
                "The retained video frame plan no longer matches the journal.",
                code="RESUME_STATE_MISMATCH",
            ) from None
