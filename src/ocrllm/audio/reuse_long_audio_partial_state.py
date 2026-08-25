"""Reuse the settled prefix of one exact long-audio request plan."""

from __future__ import annotations

from ..errors import ResumeStateError
from .long_audio_partial_state import LongAudioPartialState
from .long_audio_settled_slot import LongAudioSettledSlot


def reuse_long_audio_partial_state(
    state: LongAudioPartialState,
    current_request_fingerprints: tuple[str, ...],
) -> tuple[LongAudioSettledSlot, ...]:
    """Return settled slots only when the complete current plan is identical."""
    if type(state) is not LongAudioPartialState:
        raise TypeError("state must be an exact LongAudioPartialState") from None
    if type(current_request_fingerprints) is not tuple:
        raise TypeError(
            "current_request_fingerprints must be an exact tuple"
        ) from None
    if (
        not current_request_fingerprints
        or any(
            type(fingerprint) is not str
            for fingerprint in current_request_fingerprints
        )
        or current_request_fingerprints != state.request_fingerprints
    ):
        raise ResumeStateError(
            "The long-audio partial state belongs to a different request plan.",
            code="RESUME_STATE_MISMATCH",
        ) from None
    return state.slots
