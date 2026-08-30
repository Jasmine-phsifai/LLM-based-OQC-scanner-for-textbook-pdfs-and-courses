"""Snapshot one scalar or exact flat provider-model lane."""

from __future__ import annotations

from .errors import ConfigError
from .providers.provider_model import ProviderModel


def normalize_provider_model_lane(
    value: object,
    *,
    distinguish_runtime_settings: bool,
) -> tuple[ProviderModel, ...]:
    """Reject invalid provider topology and definite lane duplicates."""
    if type(value) is ProviderModel:
        lane = (value,)
    elif type(value) is list and value:
        lane = tuple(value)
        if any(type(candidate) is not ProviderModel for candidate in lane):
            raise _invalid_lane()
    else:
        raise _invalid_lane()

    for index, candidate in enumerate(lane):
        for previous in lane[:index]:
            same_model = (previous.vendor, previous.model) == (
                candidate.vendor,
                candidate.model,
            )
            same_route = same_model and previous.settings is candidate.settings
            duplicate = (
                same_route if distinguish_runtime_settings else same_model
            )
            if duplicate:
                raise ConfigError(
                    "A provider fallback lane cannot contain a definite duplicate.",
                    code="CONFIG_INVALID",
                    details={"provider_calls_attempted": 0},
                ) from None
    return lane


def _invalid_lane() -> ConfigError:
    return ConfigError(
        "Provider input must be one exact ProviderModel or a nonempty exact "
        "list of ProviderModel values.",
        code="CONFIG_INVALID",
        details={"provider_calls_attempted": 0},
    )
