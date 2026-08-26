"""Convert one image resume state into its strict JSON document."""

from __future__ import annotations

from .image_resume_state import ImageResumeState
from .thaw_json_value import thaw_json_value


def image_resume_state_to_document(state: ImageResumeState) -> dict[str, object]:
    """Return the validated state as JSON-compatible values."""
    if type(state) is not ImageResumeState:
        raise TypeError("state must be an exact ImageResumeState") from None
    return {
        "state_version": state.state_version,
        "identity_version": state.identity_version,
        "request_fingerprint": state.request_fingerprint,
        "processor_name": state.processor_name,
        "processor_version": state.processor_version,
        "sources": [
            {
                "uri": source.uri,
                "byte_size": source.byte_size,
                "sha256": source.sha256,
            }
            for source in state.sources
        ],
        "slots": [
            {
                "slot_id": slot.slot_id,
                "workflow_pass": slot.workflow_pass,
                "provider": slot.provider,
                "model": slot.model,
                "markdown": slot.markdown,
                "markdown_sha256": slot.markdown_sha256,
                "provider_calls_attempted": slot.provider_calls_attempted,
            }
            for slot in state.slots
        ],
        "result": {
            "markdown": state.markdown,
            "media_type": state.media_type,
            "profile": state.profile,
            "status": state.status,
            "hotwords": list(state.hotwords),
            "warnings": list(state.warnings),
            "metadata": thaw_json_value(state.metadata),
        },
        "final_markdown_sha256": state.final_markdown_sha256,
    }
