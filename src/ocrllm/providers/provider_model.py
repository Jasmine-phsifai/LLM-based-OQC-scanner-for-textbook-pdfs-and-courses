"""Immutable identity and runtime settings for one built-in provider model."""

from __future__ import annotations

from typing import Final

from ..errors import ConfigError
from .dashscope.provider_settings import DashScopeSettings
from .google_genai.provider_settings import GoogleGenAISettings


_GOOGLE_ADAPTER_ID: Final = "google_genai"
_DASHSCOPE_ADAPTER_ID: Final = "dashscope_openai_compatible"


class ProviderModel:
    """Bind one exact built-in adapter/model to its runtime-only settings.

    The safe vendor/model/adapter tuple is the value identity. Settings may
    contain a credential or a mutable credential pool, so they are available
    for dispatch but deliberately absent from repr, equality, and hashing.
    """

    __slots__ = ("_adapter_id", "_model", "_settings", "_vendor")

    def __init__(
        self,
        *,
        vendor: str,
        model: str,
        adapter_id: str,
        settings: GoogleGenAISettings | DashScopeSettings,
    ) -> None:
        _require_exact_text(vendor, field_name="vendor")
        _require_exact_text(model, field_name="model")
        _require_exact_text(adapter_id, field_name="adapter_id")
        expected_settings_type = _expected_settings_type(vendor, adapter_id)
        if type(settings) is not expected_settings_type:
            raise ConfigError(
                "ProviderModel.settings must exactly match its built-in adapter.",
                code="CONFIG_INVALID",
            ) from None
        object.__setattr__(self, "_vendor", vendor)
        object.__setattr__(self, "_model", model)
        object.__setattr__(self, "_adapter_id", adapter_id)
        object.__setattr__(self, "_settings", settings)

    @property
    def vendor(self) -> str:
        return self._vendor

    @property
    def model(self) -> str:
        return self._model

    @property
    def adapter_id(self) -> str:
        return self._adapter_id

    @property
    def settings(self) -> GoogleGenAISettings | DashScopeSettings:
        """Return the exact runtime settings without treating them as identity."""
        return self._settings

    def __repr__(self) -> str:
        return (
            "ProviderModel("
            f"vendor={self.vendor!r}, model={self.model!r}, "
            f"adapter_id={self.adapter_id!r})"
        )

    def __eq__(self, other: object) -> bool:
        if type(other) is not ProviderModel:
            return NotImplemented
        return self._identity == other._identity

    def __hash__(self) -> int:
        return hash(self._identity)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("ProviderModel is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("ProviderModel is immutable")

    @property
    def _identity(self) -> tuple[str, str, str]:
        return (self.vendor, self.model, self.adapter_id)


def _expected_settings_type(
    vendor: str,
    adapter_id: str,
) -> type[GoogleGenAISettings] | type[DashScopeSettings]:
    if vendor == "google" and adapter_id == _GOOGLE_ADAPTER_ID:
        return GoogleGenAISettings
    if vendor == "dashscope" and adapter_id == _DASHSCOPE_ADAPTER_ID:
        return DashScopeSettings
    raise ConfigError(
        "ProviderModel vendor and adapter_id must select one supported built-in route.",
        code="CONFIG_INVALID",
    ) from None


def _require_exact_text(value: object, *, field_name: str) -> None:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ConfigError(
            f"ProviderModel.{field_name} must be nonempty exact text.",
            code="CONFIG_INVALID",
        ) from None
