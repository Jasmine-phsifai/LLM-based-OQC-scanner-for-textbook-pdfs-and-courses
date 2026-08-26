"""Reuse only an exact long-audio request plan's settled prefix."""

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
from ocrllm.audio.reuse_long_audio_partial_state import (
    reuse_long_audio_partial_state,
)
from ocrllm.errors import ResumeStateError


PLAN = ("1" * 64, "2" * 64)


def _state(*, with_slot: bool = True) -> LongAudioPartialState:
    slots: tuple[LongAudioSettledSlot, ...] = ()
    if with_slot:
        markdown = "# 第一段\n\n$x^2+y^2$"
        slots = (
            LongAudioSettledSlot(
                window_index=0,
                request_fingerprint=PLAN[0],
                markdown=markdown,
                markdown_sha256=hashlib.sha256(
                    markdown.encode("utf-8")
                ).hexdigest(),
                provider="google",
                model="gemini-2.5-flash",
                transport="google_files",
                provider_calls_attempted=2,
                input_tokens=None,
                output_tokens=41,
                status="partial",
                warnings=("The provider client could not be closed.",),
                provider_file_cleanup_succeeded=True,
                provider_client_cleanup_succeeded=False,
            ),
        )
    return LongAudioPartialState(
        state_version=LONG_AUDIO_PARTIAL_STATE_VERSION,
        identity_version=LONG_AUDIO_REQUEST_IDENTITY_VERSION,
        mode="whole",
        interval_minutes=None,
        request_fingerprints=PLAN,
        slots=slots,
    )


def test_exact_plan_returns_the_same_validated_settled_prefix() -> None:
    state = _state()

    reused = reuse_long_audio_partial_state(state, PLAN)

    assert reused is state.slots
    assert reused[0].status == "partial"
    assert reused[0].warnings == ("The provider client could not be closed.",)
    assert reused[0].input_tokens is None
    assert reused[0].output_tokens == 41


def test_exact_plan_with_no_settled_slots_returns_the_empty_prefix() -> None:
    state = _state(with_slot=False)

    assert reuse_long_audio_partial_state(state, PLAN) is state.slots


@pytest.mark.parametrize(
    "current_plan",
    [
        (),
        (PLAN[0],),
        PLAN + ("3" * 64,),
        tuple(reversed(PLAN)),
        (PLAN[0], "3" * 64),
        (PLAN[0], PLAN[0]),
        ("A" * 64, PLAN[1]),
        ("short", PLAN[1]),
        (1, PLAN[1]),
        (type("Fingerprint", (str,), {})(PLAN[0]), PLAN[1]),
    ],
)
def test_nonmatching_or_malformed_tuple_is_not_reusable(current_plan) -> None:
    with pytest.raises(ResumeStateError) as caught:
        reuse_long_audio_partial_state(_state(), current_plan)

    assert caught.value.code == "RESUME_STATE_MISMATCH"


@pytest.mark.parametrize(
    "container",
    [list(PLAN), iter(PLAN), type("PlanTuple", (tuple,), {})(PLAN)],
)
def test_plan_container_must_be_an_exact_tuple(container) -> None:
    with pytest.raises(TypeError, match="exact tuple"):
        reuse_long_audio_partial_state(_state(), container)


def test_state_must_be_the_exact_validated_audio_state_type() -> None:
    with pytest.raises(TypeError, match="LongAudioPartialState"):
        reuse_long_audio_partial_state(object(), PLAN)
