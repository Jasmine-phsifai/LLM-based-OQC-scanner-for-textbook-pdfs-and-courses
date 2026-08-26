"""Parse one strict long-audio partial-state document."""

from __future__ import annotations

import json

from ..errors import ResumeStateError
from .long_audio_partial_state import LongAudioPartialState
from .parse_long_audio_partial_state_document import (
    parse_long_audio_partial_state_document,
)


def parse_long_audio_partial_state(raw: bytes) -> LongAudioPartialState:
    """Reject duplicate keys, schema drift, and invalid settled slots."""
    try:
        if type(raw) is not bytes:
            raise TypeError
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        if type(document) is not dict:
            raise ValueError
        return parse_long_audio_partial_state_document(document)
    except ResumeStateError:
        raise
    except Exception:
        raise ResumeStateError(
            "The long-audio partial state is corrupt or has an unsupported schema.",
            code="RESUME_STATE_INVALID",
        ) from None


class _DuplicateKey(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey
        result[key] = value
    return result


def _reject_constant(_value: str) -> object:
    raise ValueError
