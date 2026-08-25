"""Validate one planned long-audio interval."""

from __future__ import annotations

import math

from .build_long_audio_interval_windows import LongAudioIntervalWindow


def validate_long_audio_interval_window(window: LongAudioIntervalWindow) -> None:
    """Reject values that could not safely describe one planner window."""
    if type(window) is not LongAudioIntervalWindow:
        raise TypeError("window must be an exact LongAudioIntervalWindow") from None
    if type(window.index) is not int or window.index < 0:
        raise ValueError("window index must be a non-negative integer") from None

    boundaries = (
        window.logical_start_seconds,
        window.logical_end_seconds,
        window.actual_start_seconds,
        window.actual_end_seconds,
    )
    if any(
        type(boundary) not in (int, float) or not math.isfinite(float(boundary))
        for boundary in boundaries
    ):
        raise ValueError("window boundaries must be finite numbers") from None
    if not (
        0.0 <= window.actual_start_seconds
        <= window.logical_start_seconds
        < window.logical_end_seconds
        <= window.actual_end_seconds
    ):
        raise ValueError("window boundaries are inconsistent") from None
