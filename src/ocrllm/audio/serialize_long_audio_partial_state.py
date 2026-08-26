"""Serialize one validated long-audio partial state."""

from __future__ import annotations

import json

from .long_audio_partial_state import LongAudioPartialState


def serialize_long_audio_partial_state(state: LongAudioPartialState) -> bytes:
    """Return canonical UTF-8 JSON containing only resumable paid work."""
    if type(state) is not LongAudioPartialState:
        raise TypeError("state must be an exact LongAudioPartialState") from None
    document = {
        "state_version": state.state_version,
        "identity_version": state.identity_version,
        "request_fingerprints": list(state.request_fingerprints),
        "slots": [
            {
                "window_index": slot.window_index,
                "request_fingerprint": slot.request_fingerprint,
                "markdown": slot.markdown,
                "markdown_sha256": slot.markdown_sha256,
                "provider": slot.provider,
                "model": slot.model,
                "transport": slot.transport,
                "provider_calls_attempted": slot.provider_calls_attempted,
                "input_tokens": slot.input_tokens,
                "output_tokens": slot.output_tokens,
                "status": slot.status,
                "warnings": list(slot.warnings),
                "provider_file_cleanup_succeeded": slot.provider_file_cleanup_succeeded,
                "provider_client_cleanup_succeeded": slot.provider_client_cleanup_succeeded,
            }
            for slot in state.slots
        ],
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
