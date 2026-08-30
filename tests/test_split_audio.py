"""Focused contract tests for provider-free audio range planning."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from ocrllm import AudioSlice, GOOGLE_GEMINI_2_5_FLASH, ProviderModel, split_audio
from ocrllm.errors import ConfigError, InvalidSource, UnsupportedFormat
from ocrllm.providers.google_genai.provider_settings import GoogleGenAISettings


split_module = importlib.import_module("ocrllm.split_audio")
probe_module = importlib.import_module("ocrllm.audio.probe_product_mp3")
FIXTURE = Path(__file__).parent / "fixtures" / "audio" / "a1" / "mp3" / "valid_cbr.mp3"


def _audio_provider(model: str, *, default_minutes: int) -> ProviderModel:
    return ProviderModel(
        vendor="google",
        model=model,
        adapter_id="google_genai",
        settings=GoogleGenAISettings(),
        supports_plain_ocr=True,
        supports_detail_ocr=True,
        supports_audio=True,
        default_image_batch_size=1,
        default_audio_minutes=default_minutes,
        retry_rules={},
    )


def test_split_audio_whole_accepts_a_real_short_mp3_without_artifacts(tmp_path):
    source = tmp_path / "short.mp3"
    source.write_bytes(FIXTURE.read_bytes())
    source_bytes = source.read_bytes()
    before = tuple(path.name for path in tmp_path.iterdir())

    slices = split_audio(source, interval_minutes=-1)

    assert len(slices) == 1
    assert type(slices[0]) is AudioSlice
    assert slices[0].source == source
    assert slices[0].index == 0
    assert slices[0].logical_start_seconds == 0.0
    assert slices[0].actual_start_seconds == 0.0
    assert slices[0].logical_end_seconds == slices[0].actual_end_seconds
    assert slices[0].logical_end_seconds == pytest.approx(0.5, abs=0.02)
    assert source.read_bytes() == source_bytes
    assert tuple(path.name for path in tmp_path.iterdir()) == before


def test_split_audio_reuses_context_windows(monkeypatch):
    monkeypatch.setattr(split_module, "probe_product_mp3", lambda _source: 150.0)

    slices = split_audio("lecture.mp3", interval_minutes=1)

    assert tuple(
        (
            item.index,
            item.logical_start_seconds,
            item.logical_end_seconds,
            item.actual_start_seconds,
            item.actual_end_seconds,
        )
        for item in slices
    ) == (
        (0, 0.0, 60.0, 0.0, 90.0),
        (1, 60.0, 120.0, 30.0, 150.0),
        (2, 120.0, 150.0, 90.0, 150.0),
    )


def test_split_audio_uses_smallest_provider_default_and_explicit_wins(monkeypatch):
    monkeypatch.setattr(split_module, "probe_product_mp3", lambda _source: 1200.0)
    providers = [
        _audio_provider("gemini-a", default_minutes=30),
        _audio_provider("gemini-b", default_minutes=10),
    ]

    assert len(split_audio("lecture.mp3", provider=providers)) == 2
    assert len(
        split_audio(
            "lecture.mp3",
            provider=providers,
            interval_minutes=5,
        )
    ) == 4


@pytest.mark.parametrize("value", (True, 0, -2, 1.5, "5"))
def test_split_audio_rejects_invalid_intervals_before_source(value):
    with pytest.raises(ConfigError) as captured:
        split_audio("missing.mp3", interval_minutes=value)  # type: ignore[arg-type]
    assert captured.value.code == "CONFIG_INVALID"
    assert captured.value.details["provider_calls_attempted"] == 0


def test_split_audio_rejects_missing_or_invalid_provider_before_source():
    with pytest.raises(ConfigError) as missing:
        split_audio("missing.mp3")
    assert missing.value.code == "CONFIG_MISSING"

    invalid_values = ([], (), [GOOGLE_GEMINI_2_5_FLASH, object()])
    for value in invalid_values:
        with pytest.raises(ConfigError) as invalid:
            split_audio("missing.mp3", provider=value)  # type: ignore[arg-type]
        assert invalid.value.code == "CONFIG_INVALID"
        assert invalid.value.details["provider_calls_attempted"] == 0


def test_split_audio_checks_audio_capability_and_planning_duplicates_before_source():
    no_audio = ProviderModel(
        vendor="google",
        model="image-only",
        adapter_id="google_genai",
        settings=GoogleGenAISettings(),
        supports_plain_ocr=True,
        supports_detail_ocr=False,
        supports_audio=False,
        default_image_batch_size=1,
        default_audio_minutes=None,
        retry_rules={},
    )
    with pytest.raises(ConfigError):
        split_audio("missing.mp3", provider=no_audio, interval_minutes=-1)

    duplicate = _audio_provider(
        GOOGLE_GEMINI_2_5_FLASH.model,
        default_minutes=1,
    )
    with pytest.raises(ConfigError):
        split_audio(
            "missing.mp3",
            provider=[GOOGLE_GEMINI_2_5_FLASH, duplicate],
        )


def test_split_audio_source_errors_are_typed(tmp_path):
    for value in (None, 1, object()):
        with pytest.raises(InvalidSource) as wrong_type:
            split_audio(value, interval_minutes=-1)  # type: ignore[arg-type]
        assert wrong_type.value.code == "SOURCE_INVALID"

    with pytest.raises(UnsupportedFormat):
        split_audio(tmp_path / "audio.wav", interval_minutes=-1)
    with pytest.raises(InvalidSource) as missing:
        split_audio(tmp_path / "missing.mp3", interval_minutes=-1)
    assert missing.value.code == "SOURCE_NOT_FOUND"

    damaged = tmp_path / "damaged.mp3"
    damaged.write_bytes(b"not an mp3")
    with pytest.raises(InvalidSource) as invalid:
        split_audio(damaged, interval_minutes=-1)
    assert invalid.value.code == "SOURCE_INVALID"


def test_product_mp3_probe_accepts_ten_hours_and_rejects_above(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "long.mp3"
    source.write_bytes(b"x")
    monkeypatch.setattr(probe_module, "load_miniaudio", lambda: object())
    observed: list[Path] = []

    def duration(path, *, backend):
        assert backend is not None
        observed.append(path)
        return 36_000.0

    monkeypatch.setattr(probe_module, "decode_mp3_duration", duration)
    assert probe_module.probe_product_mp3(source) == 36_000.0

    monkeypatch.setattr(
        probe_module,
        "decode_mp3_duration",
        lambda _path, *, backend: 36_000.1,
    )
    with pytest.raises(InvalidSource) as too_long:
        probe_module.probe_product_mp3(source)
    assert too_long.value.code == "SOURCE_TOO_LARGE"
    assert too_long.value.details["maximum_duration_seconds"] == 36_000.0
    assert observed == [source]
