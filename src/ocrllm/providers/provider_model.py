"""Immutable identity and runtime settings for one built-in provider model."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, Literal

from ..errors import ConfigError, ProviderError
from ..image_group_limits import MAX_IMAGE_GROUP_COUNT
from .dashscope.provider_settings import DashScopeSettings
from .google_genai.provider_settings import GoogleGenAISettings
from .openai_compatible.provider_settings import OpenAICompatibleSettings


_GOOGLE_ADAPTER_ID: Final = "google_genai"
_DASHSCOPE_ADAPTER_ID: Final = "dashscope_openai_compatible"
_OPENAI_COMPATIBLE_ADAPTER_ID: Final = "openai_compatible_chat"
_RETRY_LABELS: Final = frozenset({"error", "next", "current"})
_RETRY_RULE_CODES: Final = ProviderError.allowed_codes - {
    "ALL_CANDIDATES_EXHAUSTED"
}

ProviderRetryLabel = Literal["error", "next", "current"]
ProviderRetryRule = tuple[ProviderRetryLabel, int, int]


class ProviderModel:
    """Describe one exact built-in model and its bounded planning facts.

    The safe vendor/model/adapter tuple is the value identity. Settings may
    contain a credential or a mutable credential pool, so they are available
    for dispatch but deliberately absent from repr, equality, and hashing.
    Retry rules are immutable data; this value never performs retries.
    """

    __slots__ = (
        "_adapter_id",
        "_default_audio_minutes",
        "_default_image_batch_size",
        "_model",
        "_retry_rules",
        "_settings",
        "_supports_audio",
        "_supports_detail_ocr",
        "_supports_plain_ocr",
        "_vendor",
    )

    def __init__(
        self,
        *,
        vendor: str,
        model: str,
        adapter_id: str,
        settings: (
            GoogleGenAISettings | DashScopeSettings | OpenAICompatibleSettings
        ),
        supports_plain_ocr: bool,
        supports_detail_ocr: bool,
        supports_audio: bool,
        default_image_batch_size: int | None,
        default_audio_minutes: int | None,
        retry_rules: dict[str, ProviderRetryRule],
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
        _require_exact_bool(supports_plain_ocr, field_name="supports_plain_ocr")
        _require_exact_bool(supports_detail_ocr, field_name="supports_detail_ocr")
        _require_exact_bool(supports_audio, field_name="supports_audio")
        if supports_detail_ocr and not supports_plain_ocr:
            raise ConfigError(
                "ProviderModel detail OCR support requires plain OCR support.",
                code="CONFIG_INVALID",
            ) from None
        _validate_image_default(
            default_image_batch_size,
            supported=supports_plain_ocr,
        )
        _validate_audio_default(
            default_audio_minutes,
            supported=supports_audio,
        )
        normalized_retry_rules = _normalize_retry_rules(retry_rules)
        object.__setattr__(self, "_vendor", vendor)
        object.__setattr__(self, "_model", model)
        object.__setattr__(self, "_adapter_id", adapter_id)
        object.__setattr__(self, "_settings", settings)
        object.__setattr__(self, "_supports_plain_ocr", supports_plain_ocr)
        object.__setattr__(self, "_supports_detail_ocr", supports_detail_ocr)
        object.__setattr__(self, "_supports_audio", supports_audio)
        object.__setattr__(
            self,
            "_default_image_batch_size",
            default_image_batch_size,
        )
        object.__setattr__(self, "_default_audio_minutes", default_audio_minutes)
        object.__setattr__(self, "_retry_rules", normalized_retry_rules)

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
    def settings(
        self,
    ) -> GoogleGenAISettings | DashScopeSettings | OpenAICompatibleSettings:
        """Return the exact runtime settings without treating them as identity."""
        return self._settings

    @property
    def supports_plain_ocr(self) -> bool:
        return self._supports_plain_ocr

    @property
    def supports_detail_ocr(self) -> bool:
        return self._supports_detail_ocr

    @property
    def supports_audio(self) -> bool:
        return self._supports_audio

    @property
    def default_image_batch_size(self) -> int | None:
        return self._default_image_batch_size

    @property
    def default_audio_minutes(self) -> int | None:
        return self._default_audio_minutes

    @property
    def retry_rules(self) -> Mapping[str, ProviderRetryRule]:
        return self._retry_rules

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
) -> (
    type[GoogleGenAISettings]
    | type[DashScopeSettings]
    | type[OpenAICompatibleSettings]
):
    if vendor == "google" and adapter_id == _GOOGLE_ADAPTER_ID:
        return GoogleGenAISettings
    if vendor == "dashscope" and adapter_id == _DASHSCOPE_ADAPTER_ID:
        return DashScopeSettings
    if adapter_id == _OPENAI_COMPATIBLE_ADAPTER_ID:
        return OpenAICompatibleSettings
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


def _require_exact_bool(value: object, *, field_name: str) -> None:
    if type(value) is not bool:
        raise ConfigError(
            f"ProviderModel.{field_name} must be a boolean.",
            code="CONFIG_INVALID",
        ) from None


def _validate_image_default(value: object, *, supported: bool) -> None:
    if supported:
        if type(value) is int and 1 <= value <= MAX_IMAGE_GROUP_COUNT:
            return
        raise ConfigError(
            "A plain-image ProviderModel requires a default image batch size "
            f"in [1, {MAX_IMAGE_GROUP_COUNT}].",
            code="CONFIG_INVALID",
        ) from None
    if value is not None:
        raise ConfigError(
            "A ProviderModel without plain OCR support cannot have an image default.",
            code="CONFIG_INVALID",
        ) from None


def _validate_audio_default(value: object, *, supported: bool) -> None:
    if supported:
        if type(value) is int and value > 0:
            return
        raise ConfigError(
            "An audio ProviderModel requires a positive integer-minute default.",
            code="CONFIG_INVALID",
        ) from None
    if value is not None:
        raise ConfigError(
            "A ProviderModel without audio support cannot have an audio default.",
            code="CONFIG_INVALID",
        ) from None


def _normalize_retry_rules(
    value: object,
) -> Mapping[str, ProviderRetryRule]:
    if type(value) is not dict:
        raise ConfigError(
            "ProviderModel.retry_rules must be an exact dict.",
            code="CONFIG_INVALID",
        ) from None
    normalized: dict[str, ProviderRetryRule] = {}
    for code, rule in value.items():
        if type(code) is not str or code not in _RETRY_RULE_CODES:
            raise ConfigError(
                "ProviderModel.retry_rules keys must be canonical provider codes.",
                code="CONFIG_INVALID",
            ) from None
        if (
            type(rule) is not tuple
            or len(rule) != 3
            or type(rule[0]) is not str
            or rule[0] not in _RETRY_LABELS
            or type(rule[1]) is not int
            or rule[1] < 0
            or type(rule[2]) is not int
            or rule[2] < 0
        ):
            raise ConfigError(
                "Each provider retry rule must be "
                "(label, extra_retries, wait_seconds) with finite integers.",
                code="CONFIG_INVALID",
            ) from None
        normalized[code] = rule
    return MappingProxyType(normalized)
