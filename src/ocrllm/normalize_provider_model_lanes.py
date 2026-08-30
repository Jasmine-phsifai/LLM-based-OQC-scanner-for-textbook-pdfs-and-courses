"""Snapshot scalar, flat, or exact nested provider-model topology."""

from __future__ import annotations

from .errors import ConfigError
from .providers.provider_model import ProviderModel


MAX_PROVIDER_LANES = 32


def normalize_provider_model_lanes(
    value: object,
    *,
    distinguish_runtime_settings: bool,
) -> tuple[tuple[ProviderModel, ...], ...]:
    """Return exact immutable lanes after complete topology validation."""
    if type(value) is ProviderModel:
        lanes = ((value,),)
    elif type(value) is list and value:
        if all(type(candidate) is ProviderModel for candidate in value):
            lanes = (tuple(value),)
        elif all(type(lane) is list and lane for lane in value):
            lanes = tuple(tuple(lane) for lane in value)
            if any(
                any(type(candidate) is not ProviderModel for candidate in lane)
                for lane in lanes
            ):
                raise _invalid_lanes()
        else:
            raise _invalid_lanes()
    else:
        raise _invalid_lanes()

    if len(lanes) > MAX_PROVIDER_LANES:
        raise ConfigError(
            "A nested provider plan exceeds the 32-lane safety limit.",
            code="CONFIG_INVALID",
            details={"provider_calls_attempted": 0},
        ) from None
    for lane in lanes:
        _reject_lane_duplicates(
            lane,
            distinguish_runtime_settings=distinguish_runtime_settings,
        )
    return lanes


def _reject_lane_duplicates(
    lane: tuple[ProviderModel, ...],
    *,
    distinguish_runtime_settings: bool,
) -> None:
    for index, candidate in enumerate(lane):
        for previous in lane[:index]:
            same_model = (previous.vendor, previous.model) == (
                candidate.vendor,
                candidate.model,
            )
            same_route = same_model and previous.settings is candidate.settings
            duplicate = same_route if distinguish_runtime_settings else same_model
            if duplicate:
                raise ConfigError(
                    "A provider fallback lane cannot contain a definite duplicate.",
                    code="CONFIG_INVALID",
                    details={"provider_calls_attempted": 0},
                ) from None


def _invalid_lanes() -> ConfigError:
    return ConfigError(
        "Provider input must be one exact ProviderModel, one nonempty exact "
        "list of ProviderModel values, or one nonempty exact list of nonempty "
        "ProviderModel lists.",
        code="CONFIG_INVALID",
        details={"provider_calls_attempted": 0},
    )
