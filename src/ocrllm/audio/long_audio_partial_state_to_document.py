"""Convert long-audio state into its strict JSON document."""

from __future__ import annotations

from .long_audio_partial_state import LongAudioPartialState


def long_audio_partial_state_to_document(
    state: LongAudioPartialState,
) -> dict[str, object]:
    """Return the validated state as JSON-compatible values."""
    if type(state) is not LongAudioPartialState:
        raise TypeError("state must be an exact LongAudioPartialState") from None
    return {
        "state_version": state.state_version,
        "identity_version": state.identity_version,
        "mode": state.mode,
        "interval_minutes": state.interval_minutes,
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
                "provider_file_cleanup_succeeded": (
                    slot.provider_file_cleanup_succeeded
                ),
                "provider_client_cleanup_succeeded": (
                    slot.provider_client_cleanup_succeeded
                ),
            }
            for slot in state.slots
        ],
    }
