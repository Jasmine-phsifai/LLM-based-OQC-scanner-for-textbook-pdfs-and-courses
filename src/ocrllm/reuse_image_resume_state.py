"""Validate and reconstruct one completed image processor output."""

from __future__ import annotations

import hashlib

from .errors import ResumeStateError
from .image_request_identity import ImageRequestIdentity
from .image_resume_state import ImageResumeState
from .processor_output import ProcessorOutput
from .validate_image_resume_identity import validate_image_resume_identity


def reuse_image_resume_state(
    state: ImageResumeState,
    identity: ImageRequestIdentity,
) -> ProcessorOutput:
    """Return stored output only when source, request, and processor all match."""
    validate_image_resume_identity(state, identity)
    if not state.markdown:
        raise ResumeStateError(
            "The image resume state holds no completed result to reuse.",
            code="RESUME_STATE_INVALID",
        ) from None
    markdown_sha256 = hashlib.sha256(state.markdown.encode("utf-8")).hexdigest()
    if markdown_sha256 != state.final_markdown_sha256:
        raise ResumeStateError(
            "The completed result in image resume state is corrupt.",
            code="RESUME_STATE_INVALID",
        ) from None
    metadata = dict(state.metadata)
    if "current_model_token_usage" in metadata:
        metadata["current_model_token_usage"] = ()
    return ProcessorOutput(
        media_type="image",
        markdown=state.markdown,
        profile=state.profile,
        status=state.status,
        hotwords=state.hotwords,
        warnings=state.warnings,
        metadata=metadata,
    )
