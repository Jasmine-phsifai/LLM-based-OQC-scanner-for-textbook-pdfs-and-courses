"""Serialize one validated image resume state as canonical UTF-8 JSON."""

from __future__ import annotations

import json

from .image_resume_state import ImageResumeState
from .thaw_json_value import thaw_json_value


def serialize_image_resume_state(state: ImageResumeState) -> bytes:
    """Return deterministic state bytes without runtime or secret fields."""
    document = {
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
    return (
        json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
