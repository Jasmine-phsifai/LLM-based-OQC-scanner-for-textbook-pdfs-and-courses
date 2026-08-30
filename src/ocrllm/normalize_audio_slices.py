"""Normalize the exact caller-planned audio slice tuple."""

from __future__ import annotations

import math
from pathlib import Path

from .audio_slice import AudioSlice
from .errors import InvalidSource


def normalize_audio_slices(
    slices: tuple[AudioSlice, ...],
) -> tuple[AudioSlice, ...]:
    """Require one source and ordered, contiguous, finite range descriptors."""
    if type(slices) is not tuple or not slices:
        _raise_invalid("Audio recognition requires a nonempty exact slice tuple.")
    if any(type(item) is not AudioSlice for item in slices):
        _raise_invalid("Every audio slice must be an exact AudioSlice.")

    source = slices[0].source
    if not isinstance(source, Path):
        _raise_invalid("Every audio slice source must be a Path.")
    previous_logical_end = 0.0
    for expected_index, item in enumerate(slices):
        if not isinstance(item.source, Path) or item.source != source:
            _raise_invalid("Every audio slice must refer to the same source Path.")
        if type(item.index) is not int or item.index != expected_index:
            _raise_invalid("Audio slice indexes must be contiguous from zero.")
        boundaries = (
            item.logical_start_seconds,
            item.logical_end_seconds,
            item.actual_start_seconds,
            item.actual_end_seconds,
        )
        if any(
            type(value) not in (int, float) or not math.isfinite(float(value))
            for value in boundaries
        ):
            _raise_invalid("Audio slice boundaries must be finite numbers.")
        if not (
            0.0 <= item.actual_start_seconds
            <= item.logical_start_seconds
            < item.logical_end_seconds
            <= item.actual_end_seconds
        ):
            _raise_invalid("Audio slice boundaries are inconsistent.")
        if item.logical_start_seconds != previous_logical_end:
            _raise_invalid("Audio slice logical ranges must be contiguous from zero.")
        previous_logical_end = item.logical_end_seconds
    return slices


def _raise_invalid(message: str) -> None:
    raise InvalidSource(
        message,
        code="SOURCE_INVALID",
        details={"provider_calls_attempted": 0},
    ) from None
