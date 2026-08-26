"""Parse one strict long-audio partial-state document."""

from __future__ import annotations

import json

from ..errors import ResumeStateError
from .long_audio_partial_state import (
    LONG_AUDIO_PARTIAL_STATE_VERSION,
    LongAudioPartialState,
)
from .long_audio_settled_slot import LongAudioSettledSlot


_ROOT_KEYS = frozenset(
    {
        "state_version",
        "identity_version",
        "mode",
        "interval_minutes",
        "request_fingerprints",
        "slots",
    }
)
_V2_ROOT_KEYS = frozenset(
    {"state_version", "identity_version", "request_fingerprints", "slots"}
)
_SLOT_KEYS = frozenset(
    {
        "window_index",
        "request_fingerprint",
        "markdown",
        "markdown_sha256",
        "provider",
        "model",
        "transport",
        "provider_calls_attempted",
        "input_tokens",
        "output_tokens",
        "status",
        "warnings",
        "provider_file_cleanup_succeeded",
        "provider_client_cleanup_succeeded",
    }
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
        root_keys = frozenset(document)
        migrated_v2 = (
            root_keys == _V2_ROOT_KEYS
            and document["state_version"] == "ocrllm.long-audio-partial.v2"
        )
        if root_keys != _ROOT_KEYS and not migrated_v2:
            raise ValueError
        if (
            not migrated_v2
            and document["state_version"] != LONG_AUDIO_PARTIAL_STATE_VERSION
        ):
            raise ValueError
        request_fingerprints = document["request_fingerprints"]
        slot_documents = document["slots"]
        if type(request_fingerprints) is not list or type(slot_documents) is not list:
            raise ValueError

        slots = []
        for slot in slot_documents:
            if type(slot) is not dict or frozenset(slot) != _SLOT_KEYS:
                raise ValueError
            warnings = slot["warnings"]
            if type(warnings) is not list:
                raise ValueError
            slots.append(
                LongAudioSettledSlot(
                    window_index=slot["window_index"],
                    request_fingerprint=slot["request_fingerprint"],
                    markdown=slot["markdown"],
                    markdown_sha256=slot["markdown_sha256"],
                    provider=slot["provider"],
                    model=slot["model"],
                    transport=slot["transport"],
                    provider_calls_attempted=slot["provider_calls_attempted"],
                    input_tokens=slot["input_tokens"],
                    output_tokens=slot["output_tokens"],
                    status=slot["status"],
                    warnings=tuple(warnings),
                    provider_file_cleanup_succeeded=slot[
                        "provider_file_cleanup_succeeded"
                    ],
                    provider_client_cleanup_succeeded=slot[
                        "provider_client_cleanup_succeeded"
                    ],
                )
            )
        return LongAudioPartialState(
            state_version=LONG_AUDIO_PARTIAL_STATE_VERSION,
            identity_version=document["identity_version"],
            mode="whole" if migrated_v2 else document["mode"],
            interval_minutes=None if migrated_v2 else document["interval_minutes"],
            request_fingerprints=tuple(request_fingerprints),
            slots=tuple(slots),
        )
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
