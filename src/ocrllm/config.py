"""Immutable direct-Python configuration for OCRLLM calls."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from .audio_model_settings import AudioModelSettings
from .errors import ConfigError
from .freeze_json_value import FrozenJSONValue, JSONValue, freeze_json_value
from .local_ocr_settings import LocalOCRSettings
from .providers.dashscope.provider_settings import DashScopeSettings
from .providers.google_genai.provider_settings import GoogleGenAISettings
from .recognition_execution_policy import RecognitionExecutionPolicy
from .recognition_preferences import RecognitionPreferences
from .vision_model_settings import VisionModelSettings

if TYPE_CHECKING:
    from .providers.vision_provider import VisionProvider


_LANGUAGE_SUBTAG = re.compile(r"^[A-Za-z0-9]{1,8}$")


@dataclass(frozen=True, slots=True)
class Config:
    """Runtime options for OCRLLM library calls."""

    provider: DashScopeSettings | GoogleGenAISettings | VisionProvider | None = field(
        default=None,
        repr=False,
    )
    vision_model: VisionModelSettings = field(default_factory=VisionModelSettings)
    audio_model: AudioModelSettings = field(default_factory=AudioModelSettings)
    image_mode: Literal["vision", "ocr"] = "vision"
    local_ocr: LocalOCRSettings | None = field(default=None, repr=False)
    execution: RecognitionExecutionPolicy = field(
        default_factory=RecognitionExecutionPolicy
    )
    preferences: RecognitionPreferences = field(default_factory=RecognitionPreferences)
    profile: str | None = None
    input_languages: tuple[str, ...] = ()
    output_language: str | None = None
    output_dir: str | Path | None = None
    temp_dir: str | Path | None = None
    timeout_seconds: float = 120.0
    resume: bool = False
    overwrite: bool = False
    cancellation: object | None = field(default=None, repr=False)
    extra: Mapping[str, JSONValue] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        provider = _normalize_provider(self.provider)
        vision_model = _normalize_vision_model(self.vision_model)
        audio_model = _normalize_audio_model(self.audio_model)
        _validate_optional_nonempty_text(self.profile, field_name="profile")
        image_mode = _normalize_image_mode(self.image_mode)
        local_ocr = _normalize_local_ocr_pair(image_mode, self.local_ocr)
        execution = _normalize_execution_policy(self.execution)
        preferences = _normalize_preferences(self.preferences)
        _validate_dashscope_scout_workflow(
            provider=provider,
            preferences=preferences,
        )

        input_languages = _normalize_input_languages(self.input_languages)
        output_language = _normalize_output_language(self.output_language)
        timeout_seconds = _normalize_timeout(self.timeout_seconds)

        _require_boolean(self.resume, field_name="resume")
        _require_boolean(self.overwrite, field_name="overwrite")

        _validate_optional_path(self.output_dir, field_name="output_dir")
        _validate_optional_path(self.temp_dir, field_name="temp_dir")

        if self.resume and self.output_dir is None:
            raise ConfigError("Config.resume requires Config.output_dir") from None
        if self.resume and self.overwrite:
            raise ConfigError("Config.resume and Config.overwrite cannot both be true") from None

        _validate_image_mode_fields(
            image_mode=image_mode,
            provider=provider,
            vision_model=vision_model,
            preferences=preferences,
            input_languages=input_languages,
            output_language=output_language,
            resume=self.resume,
        )

        extra = _freeze_extra(self.extra)
        object.__setattr__(self, "input_languages", input_languages)
        object.__setattr__(self, "output_language", output_language)
        object.__setattr__(self, "timeout_seconds", timeout_seconds)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "vision_model", vision_model)
        object.__setattr__(self, "audio_model", audio_model)
        object.__setattr__(self, "image_mode", image_mode)
        object.__setattr__(self, "local_ocr", local_ocr)
        object.__setattr__(self, "execution", execution)
        object.__setattr__(self, "preferences", preferences)
        object.__setattr__(self, "extra", extra)

    def output_directory(self) -> Path | None:
        """Return the configured output directory, or None for in-memory mode."""
        if self.output_dir is None:
            return None
        return Path(self.output_dir)


def _normalize_preferences(value: object) -> RecognitionPreferences:
    if type(value) is not RecognitionPreferences:
        raise ConfigError(
            "Config.preferences must be an exact RecognitionPreferences instance",
            code="CONFIG_INVALID",
        ) from None
    return RecognitionPreferences(
        draft_candidates=value.draft_candidates,
        review_passes=value.review_passes,
    )


def _normalize_execution_policy(value: object) -> RecognitionExecutionPolicy:
    if type(value) is not RecognitionExecutionPolicy:
        raise ConfigError(
            "Config.execution must be an exact RecognitionExecutionPolicy instance",
            code="CONFIG_INVALID",
        ) from None
    return RecognitionExecutionPolicy(
        maximum_images_per_request=value.maximum_images_per_request,
        max_parallel_requests=value.max_parallel_requests,
        provider_request_start_interval_seconds=(
            value.provider_request_start_interval_seconds
        ),
    )


def _normalize_vision_model(value: object) -> VisionModelSettings:
    if type(value) is not VisionModelSettings:
        raise ConfigError(
            "Config.vision_model must be an exact VisionModelSettings instance",
            code="CONFIG_INVALID",
        ) from None
    return VisionModelSettings(
        name=value.name,
        candidate_models=value.candidate_models,
        maximum_images_per_request=value.maximum_images_per_request,
    )


def _normalize_audio_model(value: object) -> AudioModelSettings:
    if type(value) is not AudioModelSettings:
        raise ConfigError(
            "Config.audio_model must be an exact AudioModelSettings instance",
            code="CONFIG_INVALID",
        ) from None
    return AudioModelSettings(name=value.name)


def _normalize_provider(value: object | None) -> object | None:
    if value is None:
        return None
    if type(value) is DashScopeSettings:
        return DashScopeSettings(
            region=value.region,
            base_url=value.base_url,
            api_key=value.api_key,
            credential_pool=value.credential_pool,
            enable_thinking=value.enable_thinking,
            vl_high_resolution_images=value.vl_high_resolution_images,
            standalone_sign_scout_model=value.standalone_sign_scout_model,
        )
    if type(value) is GoogleGenAISettings:
        return GoogleGenAISettings(api_key=value.api_key)
    if isinstance(value, DashScopeSettings):
        raise ConfigError(
            "Config.provider must use an exact DashScopeSettings instance.",
            code="CONFIG_INVALID",
        ) from None
    if isinstance(value, GoogleGenAISettings):
        raise ConfigError(
            "Config.provider must use an exact GoogleGenAISettings instance.",
            code="CONFIG_INVALID",
        ) from None
    if isinstance(value, str):
        raise ConfigError(
            "Config.provider must be adapter settings or an injected provider object; "
            "string provider categories are not supported.",
            code="CONFIG_INVALID",
        ) from None
    return value


def _normalize_image_mode(value: object) -> Literal["vision", "ocr"]:
    if type(value) is not str or value not in {"vision", "ocr"}:
        raise ConfigError(
            "Config.image_mode must be exactly 'vision' or 'ocr'.",
            code="CONFIG_INVALID",
        ) from None
    return cast(Literal["vision", "ocr"], value)


def _normalize_local_ocr_pair(
    image_mode: Literal["vision", "ocr"],
    value: object | None,
) -> LocalOCRSettings | None:
    if image_mode == "vision":
        if value is not None:
            raise ConfigError(
                "Config.local_ocr is valid only when image_mode='ocr'.",
                code="CONFIG_INVALID",
            ) from None
        return None
    if value is None:
        return LocalOCRSettings()
    if type(value) is not LocalOCRSettings:
        raise ConfigError(
            "Config.local_ocr must be an exact LocalOCRSettings instance.",
            code="CONFIG_INVALID",
        ) from None
    return LocalOCRSettings(minimum_confidence=value.minimum_confidence)


def _validate_image_mode_fields(
    *,
    image_mode: Literal["vision", "ocr"],
    provider: object | None,
    vision_model: VisionModelSettings,
    preferences: RecognitionPreferences,
    input_languages: tuple[str, ...],
    output_language: str | None,
    resume: bool,
) -> None:
    if image_mode != "ocr":
        return
    if provider is not None or vision_model != VisionModelSettings():
        raise ConfigError(
            "OCR mode cannot use provider or vision-model settings.",
            code="CONFIG_INVALID",
        ) from None
    if preferences != RecognitionPreferences():
        raise ConfigError(
            "OCR mode cannot use LLM draft or review preferences.",
            code="CONFIG_INVALID",
        ) from None
    if input_languages or output_language is not None:
        raise ConfigError(
            "OCR mode does not accept language hints in the current engine.",
            code="CONFIG_INVALID",
        ) from None


def _validate_optional_nonempty_text(
    value: object | None,
    *,
    field_name: str,
) -> None:
    if value is None:
        return
    if type(value) is not str or not value.strip():
        raise ConfigError(f"Config.{field_name} must be nonempty text when set") from None


def _validate_dashscope_scout_workflow(
    *,
    provider: object | None,
    preferences: RecognitionPreferences,
) -> None:
    if (
        type(provider) is not DashScopeSettings
        or provider.standalone_sign_scout_model is None
    ):
        return
    if preferences != RecognitionPreferences():
        raise ConfigError(
            "DashScope standalone-sign scouting requires default "
            "RecognitionPreferences",
            code="CONFIG_INVALID",
        ) from None


def _normalize_input_languages(value: object) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ConfigError(
            "Config.input_languages must be an ordered sequence of language tags"
        ) from None
    try:
        languages = tuple(value)
    except Exception:
        raise ConfigError("Config.input_languages could not be read safely") from None

    seen: set[str] = set()
    for language in languages:
        _validate_language_tag(language, field_name="input_languages")
        normalized = language.casefold()
        if normalized in seen:
            raise ConfigError("Config.input_languages must not contain duplicates") from None
        seen.add(normalized)
    return cast(tuple[str, ...], languages)


def _normalize_output_language(value: object | None) -> str | None:
    if value is None:
        return None
    _validate_language_tag(value, field_name="output_language")
    return cast(str, value)


def _validate_language_tag(value: object, *, field_name: str) -> None:
    if type(value) is not str or value != value.strip() or not value:
        raise ConfigError(f"Config.{field_name} contains an invalid language tag") from None

    subtags = value.split("-")
    first = subtags[0]
    ordinary_language = first.isalpha() and 2 <= len(first) <= 8
    private_or_grandfathered = first.casefold() in {"x", "i"} and len(subtags) > 1
    if not (ordinary_language or private_or_grandfathered):
        raise ConfigError(f"Config.{field_name} contains an invalid language tag") from None
    if any(_LANGUAGE_SUBTAG.fullmatch(subtag) is None for subtag in subtags):
        raise ConfigError(f"Config.{field_name} contains an invalid language tag") from None


def _normalize_timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError("Config.timeout_seconds must be a finite number") from None
    normalized = float(value)
    if not math.isfinite(normalized) or not 0 < normalized <= 600:
        raise ConfigError("Config.timeout_seconds must be in the interval (0, 600]") from None
    return normalized


def _require_boolean(value: object, *, field_name: str) -> None:
    if not isinstance(value, bool):
        raise ConfigError(f"Config.{field_name} must be a boolean") from None


def _validate_optional_path(value: object | None, *, field_name: str) -> None:
    if value is None or isinstance(value, Path):
        return
    if type(value) is not str or not value.strip():
        raise ConfigError(f"Config.{field_name} must be a nonempty path when set") from None


def _freeze_extra(value: object) -> Mapping[str, FrozenJSONValue]:
    if not isinstance(value, Mapping):
        raise ConfigError("Config.extra must be a JSON object") from None
    try:
        frozen = freeze_json_value(value)
    except (TypeError, ValueError):
        raise ConfigError("Config.extra must contain only finite JSON values") from None
    if not isinstance(frozen, Mapping):
        raise ConfigError("Config.extra must be a JSON object") from None
    return cast(Mapping[str, FrozenJSONValue], frozen)
