"""Build the prompt for one context-padded long-audio interval."""

from __future__ import annotations

from .build_long_audio_interval_windows import LongAudioIntervalWindow
from .transcription_prompt import NO_SPEECH_SENTINEL
from .validate_long_audio_interval_window import validate_long_audio_interval_window


LONG_AUDIO_INTERVAL_PROMPT_VERSION = "audio.long.interval.v1"


def build_long_audio_interval_prompt(window: LongAudioIntervalWindow) -> str:
    """Request only the logical speech inside one wider uploaded MP3."""
    validate_long_audio_interval_window(window)
    clip_logical_start = (
        window.logical_start_seconds - window.actual_start_seconds
    )
    clip_logical_end = window.logical_end_seconds - window.actual_start_seconds
    return (
        "Transcribe the requested speech range faithfully as Markdown. "
        "The uploaded MP3 contains original-source audio from "
        f"{window.actual_start_seconds:.3f} to "
        f"{window.actual_end_seconds:.3f} seconds on the original source "
        "timeline. Therefore, 0.000 seconds in the uploaded MP3 maps to "
        f"{window.actual_start_seconds:.3f} seconds in the original source. "
        "Transcribe only content occurring from "
        f"{window.logical_start_seconds:.3f} to "
        f"{window.logical_end_seconds:.3f} seconds on the original source "
        "timeline. That requested range runs from "
        f"{clip_logical_start:.3f} to {clip_logical_end:.3f} seconds after "
        "the start of this uploaded MP3. Audio outside that clip-relative "
        "range is context only: use it to understand speech at the boundaries, "
        "but do not include its words in the returned transcript. Return only "
        "the transcript for the requested range. Do not add timestamps, range "
        "labels, segment markers, or commentary. If and only if the requested "
        f"range contains no speech, return exactly {NO_SPEECH_SENTINEL}."
    )
