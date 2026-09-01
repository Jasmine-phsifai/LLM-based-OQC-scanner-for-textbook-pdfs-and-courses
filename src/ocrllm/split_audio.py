"""Plan immutable audio ranges without creating physical clips."""

from __future__ import annotations

from pathlib import Path

from .audio.build_long_audio_interval_windows import (
    build_long_audio_interval_windows,
)
from .audio.probe_product_mp3 import probe_product_mp3
from .audio_slice import AudioSlice
from .errors import ConfigError, InvalidSource
from .normalize_provider_model_lanes import normalize_provider_model_lanes
from .providers.provider_model import ProviderModel


def split_audio(
    source: str | Path,
    *,
    interval_minutes: int | None = None,
    include_boundary_context: bool = True,
    provider: (
        ProviderModel
        | list[ProviderModel]
        | list[list[ProviderModel]]
        | None
    ) = None,
) -> tuple[AudioSlice, ...]:
    """Return one fixed whole or integer-minute MP3 plan."""
    if type(include_boundary_context) is not bool:
        raise ConfigError(
            "split_audio() include_boundary_context must be a boolean.",
            code="CONFIG_INVALID",
            details={"provider_calls_attempted": 0},
        ) from None
    provider_lanes = (
        normalize_provider_model_lanes(
            provider,
            distinguish_runtime_settings=False,
        )
        if provider is not None
        else None
    )
    candidates = (
        tuple(candidate for lane in provider_lanes for candidate in lane)
        if provider_lanes is not None
        else None
    )
    if candidates is not None and any(
        not candidate.supports_audio for candidate in candidates
    ):
        raise ConfigError(
            "Every selected ProviderModel must support audio input.",
            code="CONFIG_INVALID",
            details={"provider_calls_attempted": 0},
        ) from None

    resolved_interval = _resolve_interval_minutes(
        interval_minutes,
        provider_models=candidates,
    )
    if not isinstance(source, (str, Path)):
        raise InvalidSource(
            "split_audio() source must be a string or Path.",
            code="SOURCE_INVALID",
        ) from None
    source_path = Path(source)
    duration_seconds = probe_product_mp3(source_path)
    if resolved_interval == -1:
        return (
            AudioSlice(
                source=source_path,
                index=0,
                logical_start_seconds=0.0,
                logical_end_seconds=duration_seconds,
                actual_start_seconds=0.0,
                actual_end_seconds=duration_seconds,
            ),
        )

    windows = build_long_audio_interval_windows(
        duration_seconds=duration_seconds,
        interval_minutes=resolved_interval,
        include_boundary_context=include_boundary_context,
    )
    return tuple(
        AudioSlice(
            source=source_path,
            index=window.index,
            logical_start_seconds=window.logical_start_seconds,
            logical_end_seconds=window.logical_end_seconds,
            actual_start_seconds=window.actual_start_seconds,
            actual_end_seconds=window.actual_end_seconds,
        )
        for window in windows
    )


def _resolve_interval_minutes(
    interval_minutes: object,
    *,
    provider_models: tuple[ProviderModel, ...] | None,
) -> int:
    if interval_minutes is not None:
        if type(interval_minutes) is not int or (
            interval_minutes != -1 and interval_minutes <= 0
        ):
            raise ConfigError(
                "split_audio() interval_minutes must be -1 or a positive integer.",
                code="CONFIG_INVALID",
                details={"provider_calls_attempted": 0},
            ) from None
        return interval_minutes
    if provider_models is None:
        raise ConfigError(
            "split_audio() requires interval_minutes or provider.",
            code="CONFIG_MISSING",
            details={"provider_calls_attempted": 0},
        ) from None
    defaults = tuple(
        candidate.default_audio_minutes for candidate in provider_models
    )
    assert all(value is not None for value in defaults)
    return min(value for value in defaults if value is not None)
