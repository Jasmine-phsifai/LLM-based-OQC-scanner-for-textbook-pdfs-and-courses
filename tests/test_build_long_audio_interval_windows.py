"""Deterministic identity for future resumable long-audio intervals."""

from __future__ import annotations

import math

import pytest

from ocrllm.audio.build_long_audio_interval_windows import (
    build_long_audio_interval_windows,
)


def test_build_long_audio_interval_windows_keeps_order_and_fixed_context() -> None:
    windows = build_long_audio_interval_windows(
        duration_seconds=190.0,
        interval_minutes=1,
    )

    assert tuple(
        (
            window.index,
            window.logical_start_seconds,
            window.logical_end_seconds,
            window.actual_start_seconds,
            window.actual_end_seconds,
        )
        for window in windows
    ) == (
        (0, 0.0, 60.0, 0.0, 90.0),
        (1, 60.0, 120.0, 30.0, 150.0),
        (2, 120.0, 180.0, 90.0, 190.0),
        (3, 180.0, 190.0, 150.0, 190.0),
    )
    assert type(windows) is tuple


def test_build_long_audio_interval_windows_does_not_pad_one_logical_window() -> None:
    window = build_long_audio_interval_windows(
        duration_seconds=90.5,
        interval_minutes=2,
    )[0]

    assert (
        window.index,
        window.logical_start_seconds,
        window.logical_end_seconds,
        window.actual_start_seconds,
        window.actual_end_seconds,
    ) == (0, 0.0, 90.5, 0.0, 90.5)


def test_build_long_audio_interval_windows_can_keep_pure_logical_ranges() -> None:
    windows = build_long_audio_interval_windows(
        duration_seconds=125.0,
        interval_minutes=1,
        include_boundary_context=False,
    )

    assert tuple(
        (
            window.logical_start_seconds,
            window.logical_end_seconds,
            window.actual_start_seconds,
            window.actual_end_seconds,
        )
        for window in windows
    ) == (
        (0.0, 60.0, 0.0, 60.0),
        (60.0, 120.0, 60.0, 120.0),
        (120.0, 125.0, 120.0, 125.0),
    )

    short = build_long_audio_interval_windows(
        duration_seconds=20.0,
        interval_minutes=1,
        include_boundary_context=False,
    )
    assert len(short) == 1
    assert short[0].actual_end_seconds - short[0].actual_start_seconds == 20.0


@pytest.mark.parametrize(
    ("interval_minutes", "expected_exception"),
    [
        (True, TypeError),
        (1.0, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_build_long_audio_interval_windows_rejects_non_positive_exact_minutes(
    interval_minutes,
    expected_exception,
) -> None:
    with pytest.raises(expected_exception):
        build_long_audio_interval_windows(
            duration_seconds=301.0,
            interval_minutes=interval_minutes,
        )


@pytest.mark.parametrize("duration_seconds", [0.0, -1.0, math.inf, math.nan])
def test_build_long_audio_interval_windows_rejects_invalid_duration(
    duration_seconds,
) -> None:
    with pytest.raises(ValueError):
        build_long_audio_interval_windows(
            duration_seconds=duration_seconds,
            interval_minutes=5,
        )


def test_build_long_audio_interval_windows_requires_exact_context_boolean() -> None:
    with pytest.raises(TypeError):
        build_long_audio_interval_windows(
            duration_seconds=60.0,
            interval_minutes=1,
            include_boundary_context=1,  # type: ignore[arg-type]
        )
