"""Serialize one validated video job journal."""

from __future__ import annotations

import json

from .audio.long_audio_partial_state_to_document import (
    long_audio_partial_state_to_document,
)
from .image_resume_state_to_document import image_resume_state_to_document
from .thaw_json_value import thaw_json_value
from .video_job_state import VideoJobState


def serialize_video_job_state(state: VideoJobState) -> bytes:
    """Return canonical UTF-8 JSON for one resumable video job."""
    if type(state) is not VideoJobState:
        raise TypeError("state must be an exact VideoJobState") from None
    document = {
        "state_version": state.state_version,
        "source": _source_document(state.source),
        "frame_groups": [
            {
                "index": group.index,
                "frame_indices": list(group.frame_indices),
                "frame_timestamps_seconds": list(group.frame_timestamps_seconds),
                "identity": {
                    "request_fingerprint": group.identity.request_fingerprint,
                    "identity_version": group.identity.identity_version,
                    "processor_name": group.identity.processor_name,
                    "processor_version": group.identity.processor_version,
                    "sources": [
                        _source_document(source) for source in group.identity.sources
                    ],
                },
                "image_state": (
                    None
                    if group.image_state is None
                    else image_resume_state_to_document(group.image_state)
                ),
            }
            for group in state.frame_groups
        ],
        "audio": {
            "state": state.audio.state,
            "mode": state.audio.mode,
            "interval_minutes": state.audio.interval_minutes,
            "model": state.audio.model,
            "artifact": (
                None
                if state.audio.artifact is None
                else _source_document(state.audio.artifact)
            ),
            "duration_seconds": state.audio.duration_seconds,
            "short_state": (
                None
                if state.audio.short_state is None
                else {
                    "request_fingerprint": (
                        state.audio.short_state.request_fingerprint
                    ),
                    "markdown": state.audio.short_state.markdown,
                    "markdown_sha256": state.audio.short_state.markdown_sha256,
                    "status": state.audio.short_state.status,
                    "warnings": list(state.audio.short_state.warnings),
                    "metadata": thaw_json_value(state.audio.short_state.metadata),
                    "no_speech": state.audio.short_state.no_speech,
                }
            ),
            "long_state": (
                None
                if state.audio.long_state is None
                else long_audio_partial_state_to_document(state.audio.long_state)
            ),
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


def _source_document(source) -> dict[str, object]:
    return {
        "uri": source.uri,
        "byte_size": source.byte_size,
        "sha256": source.sha256,
    }
