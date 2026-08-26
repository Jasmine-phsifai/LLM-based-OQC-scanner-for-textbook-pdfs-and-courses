"""Parse one strict long-audio partial-state JSON document."""

from __future__ import annotations

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


def parse_long_audio_partial_state_document(
    document: object,
) -> LongAudioPartialState:
    """Validate one decoded JSON object without a second encode/decode pass."""
    try:
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
