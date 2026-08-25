"""Deterministic prompt contract for one long-audio interval."""

from __future__ import annotations

import pytest

from ocrllm.audio.build_long_audio_interval_prompt import (
    LONG_AUDIO_INTERVAL_PROMPT_VERSION,
    build_long_audio_interval_prompt,
)
from ocrllm.audio.build_long_audio_interval_windows import LongAudioIntervalWindow
from ocrllm.audio.transcription_prompt import NO_SPEECH_SENTINEL


def _interior_window() -> LongAudioIntervalWindow:
    return LongAudioIntervalWindow(
        index=1,
        logical_start_seconds=60.0,
        logical_end_seconds=120.0,
        actual_start_seconds=30.0,
        actual_end_seconds=150.0,
    )


def test_build_long_audio_interval_prompt_names_both_time_coordinates() -> None:
    prompt = build_long_audio_interval_prompt(_interior_window())

    assert LONG_AUDIO_INTERVAL_PROMPT_VERSION == "audio.long.interval.v1"
    assert (
        "from 30.000 to 150.000 seconds on the original source timeline"
        in prompt
    )
    assert (
        "from 60.000 to 120.000 seconds on the original source timeline"
        in prompt
    )
    assert (
        "from 30.000 to 90.000 seconds after the start of this uploaded MP3"
        in prompt
    )
    assert (
        "0.000 seconds in the uploaded MP3 maps to 30.000 seconds in the "
        "original source"
        in prompt
    )
    assert "context only" in prompt
    assert "do not include its words" in prompt


def test_build_long_audio_interval_prompt_limits_output_to_requested_speech() -> None:
    prompt = build_long_audio_interval_prompt(_interior_window())

    assert "Transcribe all speech in this audio" not in prompt
    assert "Return only the transcript for the requested range" in prompt
    assert (
        "Do not add timestamps, range labels, segment markers, or commentary"
        in prompt
    )
    assert f"return exactly {NO_SPEECH_SENTINEL}." in prompt


@pytest.mark.parametrize(
    "window",
    [
        object(),
        LongAudioIntervalWindow(
            index=0,
            logical_start_seconds=60.0,
            logical_end_seconds=120.0,
            actual_start_seconds=61.0,
            actual_end_seconds=150.0,
        ),
    ],
)
def test_build_long_audio_interval_prompt_rejects_untrusted_windows(window) -> None:
    with pytest.raises((TypeError, ValueError)):
        build_long_audio_interval_prompt(window)
