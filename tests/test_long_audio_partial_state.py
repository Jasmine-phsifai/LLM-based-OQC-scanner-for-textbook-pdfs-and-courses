"""Minimum in-memory state for settled long-audio requests."""

from __future__ import annotations

import hashlib

import pytest

from ocrllm.audio.fingerprint_long_audio_request import (
    LONG_AUDIO_REQUEST_IDENTITY_VERSION,
)
from ocrllm.audio.long_audio_partial_state import (
    LONG_AUDIO_PARTIAL_STATE_VERSION,
    LongAudioPartialState,
)
from ocrllm.audio.long_audio_settled_slot import LongAudioSettledSlot


REQUESTS = ("1" * 64, "2" * 64)


def _slot(
    *,
    window_index: int = 0,
    request_fingerprint: str = REQUESTS[0],
    markdown: str = "settled speech",
    status: str = "complete",
    warnings: tuple[str, ...] = (),
    input_tokens: int | None = 101,
    output_tokens: int | None = 17,
) -> LongAudioSettledSlot:
    return LongAudioSettledSlot(
        window_index=window_index,
        request_fingerprint=request_fingerprint,
        markdown=markdown,
        markdown_sha256=hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
        provider="google",
        model="gemini-2.5-flash",
        transport="google_files",
        provider_calls_attempted=1,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        status=status,
        warnings=warnings,
        provider_file_cleanup_succeeded=True,
        provider_client_cleanup_succeeded=True,
    )


def _state(*, slots: tuple[LongAudioSettledSlot, ...] = ()) -> LongAudioPartialState:
    return LongAudioPartialState(
        state_version=LONG_AUDIO_PARTIAL_STATE_VERSION,
        identity_version=LONG_AUDIO_REQUEST_IDENTITY_VERSION,
        mode="whole",
        interval_minutes=None,
        request_fingerprints=REQUESTS,
        slots=slots,
    )


def test_empty_state_binds_the_complete_ordered_request_plan() -> None:
    state = _state()

    assert LONG_AUDIO_PARTIAL_STATE_VERSION == "ocrllm.long-audio-partial.v3"
    assert state.request_fingerprints == REQUESTS
    assert state.slots == ()


def test_state_accepts_only_an_ordered_settled_prefix() -> None:
    first = _slot()
    second = _slot(window_index=1, request_fingerprint=REQUESTS[1])

    state = _state(slots=(first, second))

    assert state.slots == (first, second)


def test_slot_preserves_unknown_usage_and_honest_partial_warning() -> None:
    slot = _slot(
        status="partial",
        warnings=("The provider client could not be closed.",),
        input_tokens=None,
        output_tokens=None,
    )

    assert slot.input_tokens is None
    assert slot.output_tokens is None
    assert slot.status == "partial"
    assert slot.warnings == ("The provider client could not be closed.",)


@pytest.mark.parametrize(
    "changes",
    [
        {"window_index": 1},
        {"request_fingerprint": REQUESTS[1]},
    ],
)
def test_state_rejects_slots_that_do_not_match_the_next_plan_entry(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="ordered request plan"):
        _state(slots=(_slot(**changes),))


def test_state_rejects_duplicate_plan_fingerprints() -> None:
    with pytest.raises(ValueError, match="duplicated"):
        LongAudioPartialState(
            state_version=LONG_AUDIO_PARTIAL_STATE_VERSION,
            identity_version=LONG_AUDIO_REQUEST_IDENTITY_VERSION,
            mode="whole",
            interval_minutes=None,
            request_fingerprints=(REQUESTS[0], REQUESTS[0]),
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"markdown_sha256": "0" * 64},
        {"provider_calls_attempted": 0},
        {"input_tokens": -1},
        {"output_tokens": True},
        {"status": "complete", "warnings": ("cleanup failed",)},
        {"status": "partial", "warnings": ()},
        {"provider_file_cleanup_succeeded": 1},
        {"provider_client_cleanup_succeeded": "yes"},
    ],
)
def test_slot_rejects_inconsistent_paid_result_facts(
    changes: dict[str, object],
) -> None:
    arguments = {
        "window_index": 0,
        "request_fingerprint": REQUESTS[0],
        "markdown": "settled speech",
        "markdown_sha256": hashlib.sha256(b"settled speech").hexdigest(),
        "provider": "google",
        "model": "gemini-2.5-flash",
        "transport": "google_files",
        "provider_calls_attempted": 1,
        "input_tokens": 101,
        "output_tokens": 17,
        "status": "complete",
        "warnings": (),
        "provider_file_cleanup_succeeded": True,
        "provider_client_cleanup_succeeded": True,
    }
    arguments.update(changes)

    with pytest.raises(ValueError):
        LongAudioSettledSlot(**arguments)


@pytest.mark.parametrize(
    "field_name",
    ["request_fingerprints", "slots"],
)
def test_state_requires_exact_tuple_containers(field_name: str) -> None:
    arguments = {
        "state_version": LONG_AUDIO_PARTIAL_STATE_VERSION,
        "identity_version": LONG_AUDIO_REQUEST_IDENTITY_VERSION,
        "mode": "whole",
        "interval_minutes": None,
        "request_fingerprints": REQUESTS,
        "slots": (),
    }
    arguments[field_name] = list(arguments[field_name])

    with pytest.raises(TypeError, match=field_name):
        LongAudioPartialState(**arguments)
