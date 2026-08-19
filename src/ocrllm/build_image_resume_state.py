"""Convert one completed image processor output into durable resume state."""

from __future__ import annotations

import hashlib

from .errors import OutputError
from .image_request_identity import ImageRequestIdentity
from .image_resume_state import IMAGE_RESUME_STATE_VERSION, ImageResumeState
from .image_slot_state import ImageSlotState
from .processor_output import ProcessorOutput


def build_image_resume_state(
    identity: ImageRequestIdentity,
    processor_output: ProcessorOutput,
    *,
    slots: tuple[ImageSlotState, ...] = (),
) -> ImageResumeState:
    """Build state only for the current artifact-free image processor contract."""
    if processor_output.media_type != "image" or processor_output.profile is None:
        raise OutputError(
            "The image processor output cannot be checkpointed safely.",
            code="OUTPUT_WRITE_FAILED",
        ) from None
    if processor_output.assets:
        raise OutputError(
            "Image processor assets are not supported by resume version one.",
            code="OUTPUT_WRITE_FAILED",
        ) from None
    return ImageResumeState(
        state_version=IMAGE_RESUME_STATE_VERSION,
        identity_version=identity.identity_version,
        request_fingerprint=identity.request_fingerprint,
        processor_name=identity.processor_name,
        processor_version=identity.processor_version,
        sources=identity.sources,
        markdown=processor_output.markdown,
        media_type=processor_output.media_type,
        profile=processor_output.profile,
        status=processor_output.status,
        hotwords=processor_output.hotwords,
        warnings=processor_output.warnings,
        metadata=processor_output.metadata,
        slots=slots,
        final_markdown_sha256=hashlib.sha256(
            processor_output.markdown.encode("utf-8")
        ).hexdigest(),
    )
