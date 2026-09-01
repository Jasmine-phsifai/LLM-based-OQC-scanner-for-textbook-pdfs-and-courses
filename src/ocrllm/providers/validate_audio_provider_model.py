"""Validate one scalar provider-model audio route before side effects."""

from __future__ import annotations

from ..errors import ConfigError
from .provider_model import ProviderModel


def validate_audio_provider_model(provider_model: object) -> ProviderModel:
    """Return one exact model whose admitted adapter supports audio."""
    if type(provider_model) is not ProviderModel:
        _raise_invalid("Audio recognition requires an exact ProviderModel.")
    if not provider_model.supports_audio:
        _raise_invalid("The selected ProviderModel does not support audio input.")
    if provider_model.adapter_id not in {
        "google_genai",
        "openai_compatible_chat",
    }:
        _raise_invalid("The selected ProviderModel has no admitted audio adapter.")
    return provider_model


def _raise_invalid(message: str) -> None:
    raise ConfigError(
        message,
        code="CONFIG_INVALID",
        details={"provider_calls_attempted": 0},
    ) from None
