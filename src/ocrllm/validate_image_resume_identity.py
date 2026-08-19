"""Bind one loaded image resume state to the current request identity."""

from __future__ import annotations

from .errors import ResumeStateError
from .image_request_identity import ImageRequestIdentity
from .image_resume_state import ImageResumeState


def validate_image_resume_identity(
    state: ImageResumeState,
    identity: ImageRequestIdentity,
) -> None:
    """Reject states written for another identity version or request."""
    if state.identity_version != identity.identity_version:
        raise ResumeStateError(
            "The image resume state was written under identity "
            f"{state.identity_version} and cannot be reused under "
            f"{identity.identity_version}.",
            code="RESUME_STATE_MISMATCH",
            details={
                "state_identity_version": state.identity_version,
                "request_identity_version": identity.identity_version,
            },
        ) from None
    if (
        state.request_fingerprint != identity.request_fingerprint
        or state.processor_name != identity.processor_name
        or state.processor_version != identity.processor_version
        or state.sources != identity.sources
    ):
        raise ResumeStateError(
            "The image resume state belongs to a different request.",
            code="RESUME_STATE_MISMATCH",
        ) from None
