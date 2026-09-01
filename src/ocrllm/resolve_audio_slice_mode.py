"""Resolve one canonical whole or integer-minute audio slice plan."""

from __future__ import annotations

from .audio.build_long_audio_interval_windows import (
    build_long_audio_interval_windows,
)
from .audio.build_long_audio_interval_prompt import (
    LONG_AUDIO_INTERVAL_PROMPT_VERSION,
)
from .audio.transcription_prompt import AUDIO_TRANSCRIPTION_PROMPT_VERSION
from .audio_slice import AudioSlice
from .errors import InvalidSource


def resolve_audio_slice_mode(
    slices: tuple[AudioSlice, ...],
    *,
    duration_seconds: float,
) -> tuple[str, int | None, str]:
    """Validate the plan against decoded duration and return its prompt mode."""
    first = slices[0]
    if (
        len(slices) == 1
        and first.logical_start_seconds == 0.0
        and first.actual_start_seconds == 0.0
        and first.logical_end_seconds == duration_seconds
        and first.actual_end_seconds == duration_seconds
    ):
        return "whole", None, AUDIO_TRANSCRIPTION_PROMPT_VERSION

    first_span = first.logical_end_seconds - first.logical_start_seconds
    interval_minutes_value = first_span / 60.0
    if not interval_minutes_value.is_integer() or interval_minutes_value <= 0:
        _raise_mismatch()
    interval_minutes = int(interval_minutes_value)
    expected_plans = tuple(
        build_long_audio_interval_windows(
            duration_seconds=duration_seconds,
            interval_minutes=interval_minutes,
            include_boundary_context=include_boundary_context,
        )
        for include_boundary_context in (True, False)
    )
    if not any(
        len(expected) == len(slices)
        and all(
            item.index == window.index
            and item.logical_start_seconds == window.logical_start_seconds
            and item.logical_end_seconds == window.logical_end_seconds
            and item.actual_start_seconds == window.actual_start_seconds
            and item.actual_end_seconds == window.actual_end_seconds
            for item, window in zip(slices, expected, strict=True)
        )
        for expected in expected_plans
    ):
        _raise_mismatch()
    return "interval", interval_minutes, LONG_AUDIO_INTERVAL_PROMPT_VERSION


def _raise_mismatch() -> None:
    raise InvalidSource(
        "The audio slices do not match the decoded source duration and planner.",
        code="SOURCE_INVALID",
        details={"provider_calls_attempted": 0},
    ) from None
