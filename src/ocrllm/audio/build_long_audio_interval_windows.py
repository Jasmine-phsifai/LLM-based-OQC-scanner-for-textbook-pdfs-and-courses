"""Build deterministic logical and physical long-audio intervals."""

from __future__ import annotations

import math
from dataclasses import dataclass


INTERVAL_CONTEXT_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class LongAudioIntervalWindow:
    """One logical result range and the physical range sent for recognition."""

    index: int
    logical_start_seconds: float
    logical_end_seconds: float
    actual_start_seconds: float
    actual_end_seconds: float


def build_long_audio_interval_windows(
    *,
    duration_seconds: float,
    interval_minutes: int,
) -> tuple[LongAudioIntervalWindow, ...]:
    """Return ordered windows with fixed boundary context."""
    if type(interval_minutes) is not int:
        raise TypeError("interval_minutes must be an integer") from None
    if interval_minutes <= 0:
        raise ValueError("interval_minutes must be positive") from None
    if type(duration_seconds) not in (int, float):
        raise TypeError("duration_seconds must be a number") from None

    duration = float(duration_seconds)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("duration_seconds must be finite and positive") from None

    interval_seconds = float(interval_minutes * 60)
    windows: list[LongAudioIntervalWindow] = []
    logical_start = 0.0
    while logical_start < duration:
        logical_end = min(logical_start + interval_seconds, duration)
        windows.append(
            LongAudioIntervalWindow(
                index=len(windows),
                logical_start_seconds=logical_start,
                logical_end_seconds=logical_end,
                actual_start_seconds=max(
                    0.0,
                    logical_start - INTERVAL_CONTEXT_SECONDS,
                ),
                actual_end_seconds=min(
                    duration,
                    logical_end + INTERVAL_CONTEXT_SECONDS,
                ),
            )
        )
        logical_start = logical_end

    return tuple(windows)
