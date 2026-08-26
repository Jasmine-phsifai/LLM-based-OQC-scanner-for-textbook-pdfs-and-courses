"""Deterministic identity tests for one long-audio provider request."""

from __future__ import annotations

from dataclasses import replace

import pytest

import ocrllm.audio.fingerprint_long_audio_request as identity_module
from ocrllm.audio.build_long_audio_interval_windows import LongAudioIntervalWindow
from ocrllm.audio.fingerprint_long_audio_request import (
    LONG_AUDIO_REQUEST_IDENTITY_VERSION,
    fingerprint_long_audio_request,
)


SOURCE_SHA256 = "1" * 64


def _window() -> LongAudioIntervalWindow:
    return LongAudioIntervalWindow(
        index=1,
        logical_start_seconds=60.0,
        logical_end_seconds=120.0,
        actual_start_seconds=30.0,
        actual_end_seconds=150.0,
    )


def _interval_fingerprint(**changes: object) -> str:
    arguments = {
        "source_sha256": SOURCE_SHA256,
        "mode": "interval",
        "provider": "google-genai",
        "model": "gemini-2.5-flash",
        "transport": "google_files",
        "window": _window(),
    }
    arguments.update(changes)
    return fingerprint_long_audio_request(**arguments)


def test_equivalent_interval_requests_have_one_canonical_identity() -> None:
    first = _interval_fingerprint()
    second = _interval_fingerprint()

    assert LONG_AUDIO_REQUEST_IDENTITY_VERSION == "ocrllm.long-audio-request.v2"
    assert first == second
    assert len(first) == 64
    assert set(first) <= set("0123456789abcdef")


@pytest.mark.parametrize(
    "changes",
    [
        {"source_sha256": "2" * 64},
        {"provider": "another-provider"},
        {"model": "another-model"},
        {"transport": "another-transport"},
        {"window": replace(_window(), index=2)},
        {"window": replace(_window(), logical_start_seconds=61.0)},
        {"window": replace(_window(), logical_end_seconds=119.0)},
        {"window": replace(_window(), actual_start_seconds=29.0)},
        {"window": replace(_window(), actual_end_seconds=151.0)},
    ],
)
def test_each_interval_request_fact_changes_identity(changes: dict[str, object]) -> None:
    assert _interval_fingerprint(**changes) != _interval_fingerprint()


def test_whole_file_identity_is_distinct_and_requires_no_window() -> None:
    whole = fingerprint_long_audio_request(
        source_sha256=SOURCE_SHA256,
        mode="whole",
        provider="google-genai",
        model="gemini-2.5-flash",
        transport="google_files",
    )

    assert whole != _interval_fingerprint()


def test_relevant_prompt_version_changes_each_mode_identity(monkeypatch) -> None:
    interval = _interval_fingerprint()
    monkeypatch.setattr(
        identity_module,
        "LONG_AUDIO_INTERVAL_PROMPT_VERSION",
        "audio.long.interval.changed",
    )
    assert _interval_fingerprint() != interval

    whole_arguments = {
        "source_sha256": SOURCE_SHA256,
        "mode": "whole",
        "provider": "google-genai",
        "model": "gemini-2.5-flash",
        "transport": "google_files",
    }
    whole = fingerprint_long_audio_request(**whole_arguments)
    monkeypatch.setattr(
        identity_module,
        "AUDIO_TRANSCRIPTION_PROMPT_VERSION",
        "audio.transcription.changed",
    )
    assert fingerprint_long_audio_request(**whole_arguments) != whole


@pytest.mark.parametrize(
    ("changes", "error_type"),
    [
        ({"source_sha256": "A" * 64}, ValueError),
        ({"mode": "other"}, ValueError),
        ({"provider": " google-genai"}, ValueError),
        ({"model": ""}, ValueError),
        ({"transport": ""}, ValueError),
        ({"window": object()}, TypeError),
    ],
)
def test_invalid_identity_inputs_are_rejected_before_hashing(
    changes: dict[str, object],
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type):
        _interval_fingerprint(**changes)


def test_whole_file_identity_rejects_an_interval_window() -> None:
    with pytest.raises(ValueError, match="whole"):
        fingerprint_long_audio_request(
            source_sha256=SOURCE_SHA256,
            mode="whole",
            provider="google-genai",
            model="gemini-2.5-flash",
            transport="google_files",
            window=_window(),
        )


def test_interval_identity_requires_a_window() -> None:
    with pytest.raises(ValueError, match="interval"):
        fingerprint_long_audio_request(
            source_sha256=SOURCE_SHA256,
            mode="interval",
            provider="google-genai",
            model="gemini-2.5-flash",
            transport="google_files",
        )
