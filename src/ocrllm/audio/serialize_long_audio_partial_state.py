"""Serialize one validated long-audio partial state."""

from __future__ import annotations

import json

from .long_audio_partial_state import LongAudioPartialState
from .long_audio_partial_state_to_document import (
    long_audio_partial_state_to_document,
)


def serialize_long_audio_partial_state(state: LongAudioPartialState) -> bytes:
    """Return canonical UTF-8 JSON containing only resumable paid work."""
    if type(state) is not LongAudioPartialState:
        raise TypeError("state must be an exact LongAudioPartialState") from None
    document = long_audio_partial_state_to_document(state)
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
