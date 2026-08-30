"""Snapshot one scalar or exact flat provider-model lane."""

from __future__ import annotations

from .errors import ConfigError
from .normalize_provider_model_lanes import normalize_provider_model_lanes
from .providers.provider_model import ProviderModel


def normalize_provider_model_lane(
    value: object,
    *,
    distinguish_runtime_settings: bool,
) -> tuple[ProviderModel, ...]:
    """Reject invalid provider topology and definite lane duplicates."""
    if (
        type(value) is list
        and value
        and all(type(candidate) is list for candidate in value)
    ):
        raise _invalid_lane()
    lanes = normalize_provider_model_lanes(
        value,
        distinguish_runtime_settings=distinguish_runtime_settings,
    )
    if len(lanes) != 1:
        raise _invalid_lane()
    return lanes[0]


def _invalid_lane() -> ConfigError:
    return ConfigError(
        "Provider input must be one exact ProviderModel or a nonempty exact "
        "list of ProviderModel values.",
        code="CONFIG_INVALID",
        details={"provider_calls_attempted": 0},
    )
