"""Offline contract for the public provider-model planning slice."""

from __future__ import annotations

import dataclasses
import sys

import pytest

from ocrllm import batchify_images
from ocrllm.errors import ConfigError, InvalidSource
from ocrllm.providers.dashscope.provider_settings import DashScopeSettings
from ocrllm.providers.google_genai.provider_settings import GoogleGenAISettings
from ocrllm.providers.provider_model import ProviderModel
from ocrllm.providers.provider_model_presets import (
    DASHSCOPE_QWEN3_5_OCR_CN_BEIJING,
    GOOGLE_GEMINI_2_5_FLASH,
)
from ocrllm.providers.recognize_provider_model_images import (
    recognize_provider_model_images,
)
from write_test_image import write_test_image


def _image_fields(**overrides):
    fields = {
        "supports_plain_ocr": True,
        "supports_detail_ocr": True,
        "supports_audio": False,
        "default_image_batch_size": 1,
        "default_audio_minutes": None,
        "retry_rules": {},
    }
    fields.update(overrides)
    return fields


def test_provider_model_identity_is_immutable_and_secret_safe():
    first_secret = "test-only-google-key-a"
    second_secret = "test-only-google-key-b"
    first = ProviderModel(
        vendor="google",
        model="gemini-test-model",
        adapter_id="google_genai",
        settings=GoogleGenAISettings(api_key=first_secret),
        **_image_fields(),
    )
    second = ProviderModel(
        vendor="google",
        model="gemini-test-model",
        adapter_id="google_genai",
        settings=GoogleGenAISettings(api_key=second_secret),
        **_image_fields(),
    )

    assert first == second
    assert hash(first) == hash(second)
    assert first.settings.api_key == first_secret
    assert first_secret not in repr(first)
    assert second_secret not in repr(second)
    assert "settings" not in repr(first)
    assert not dataclasses.is_dataclass(first)
    with pytest.raises(TypeError):
        dataclasses.asdict(first)
    with pytest.raises(AttributeError):
        first.model = "replacement"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        del first._model


def test_live_proven_image_presets_are_credential_free_exact_entities():
    assert GOOGLE_GEMINI_2_5_FLASH == ProviderModel(
        vendor="google",
        model="gemini-2.5-flash",
        adapter_id="google_genai",
        settings=GoogleGenAISettings(api_key="test-only-google-key"),
        **_image_fields(
            supports_audio=True,
            default_image_batch_size=8,
            default_audio_minutes=30,
        ),
    )
    assert GOOGLE_GEMINI_2_5_FLASH.settings.api_key is None
    assert GOOGLE_GEMINI_2_5_FLASH.supports_plain_ocr is True
    assert GOOGLE_GEMINI_2_5_FLASH.supports_detail_ocr is True
    assert GOOGLE_GEMINI_2_5_FLASH.supports_audio is True
    assert GOOGLE_GEMINI_2_5_FLASH.default_image_batch_size == 8
    assert GOOGLE_GEMINI_2_5_FLASH.default_audio_minutes == 30
    assert GOOGLE_GEMINI_2_5_FLASH.retry_rules == {}

    assert DASHSCOPE_QWEN3_5_OCR_CN_BEIJING == ProviderModel(
        vendor="dashscope",
        model="qwen3.5-ocr",
        adapter_id="dashscope_openai_compatible",
        settings=DashScopeSettings.for_region(
            "cn-beijing",
            api_key="test-only-dashscope-key",
        ),
        **_image_fields(),
    )
    assert DASHSCOPE_QWEN3_5_OCR_CN_BEIJING.settings.api_key is None
    assert DASHSCOPE_QWEN3_5_OCR_CN_BEIJING.settings.region == "cn-beijing"
    assert DASHSCOPE_QWEN3_5_OCR_CN_BEIJING.supports_plain_ocr is True
    assert DASHSCOPE_QWEN3_5_OCR_CN_BEIJING.supports_detail_ocr is True
    assert DASHSCOPE_QWEN3_5_OCR_CN_BEIJING.supports_audio is False
    assert DASHSCOPE_QWEN3_5_OCR_CN_BEIJING.default_image_batch_size == 1
    assert DASHSCOPE_QWEN3_5_OCR_CN_BEIJING.default_audio_minutes is None
    assert DASHSCOPE_QWEN3_5_OCR_CN_BEIJING.retry_rules == {}


@pytest.mark.parametrize(
    "kwargs",
    (
        {
            "vendor": "google",
            "model": "gemini-test-model",
            "adapter_id": "google_genai",
            "settings": DashScopeSettings.for_region("cn-beijing"),
            **_image_fields(),
        },
        {
            "vendor": "google",
            "model": "gemini-test-model",
            "adapter_id": "unknown",
            "settings": GoogleGenAISettings(),
            **_image_fields(),
        },
        {
            "vendor": "google ",
            "model": "gemini-test-model",
            "adapter_id": "google_genai",
            "settings": GoogleGenAISettings(),
            **_image_fields(),
        },
    ),
)
def test_provider_model_rejects_mismatched_or_invalid_identity(kwargs):
    with pytest.raises(ConfigError) as captured:
        ProviderModel(**kwargs)

    assert captured.value.code == "CONFIG_INVALID"


def test_provider_model_image_consumer_rejects_non_entity_input():
    with pytest.raises(ConfigError) as captured:
        recognize_provider_model_images(
            object(),  # type: ignore[arg-type]
            (),
            prompt="Recognize this image.",
        )

    assert captured.value.code == "CONFIG_INVALID"
    assert captured.value.details["provider_calls_attempted"] == 0


def test_provider_model_image_consumer_reuses_existing_zero_call_preflight(tmp_path):
    google_genai_was_loaded = "google.genai" in sys.modules
    openai_was_loaded = "openai" in sys.modules
    provider_model = ProviderModel(
        vendor="google",
        model="gemini-test-model",
        adapter_id="google_genai",
        settings=GoogleGenAISettings(api_key="test-only-google-key"),
        **_image_fields(),
    )

    with pytest.raises(InvalidSource) as captured:
        recognize_provider_model_images(
            provider_model,
            (tmp_path / "missing.png",),
            prompt="Recognize this image.",
        )

    assert captured.value.code == "SOURCE_NOT_FOUND"
    assert captured.value.details["provider_calls_attempted"] == 0
    assert ("google.genai" in sys.modules) is google_genai_was_loaded
    assert ("openai" in sys.modules) is openai_was_loaded


def test_provider_model_image_consumer_validates_request_timeout_before_dispatch():
    google_genai_was_loaded = "google.genai" in sys.modules
    openai_was_loaded = "openai" in sys.modules
    provider_model = ProviderModel(
        vendor="google",
        model="gemini-test-model",
        adapter_id="google_genai",
        settings=GoogleGenAISettings(api_key="test-only-google-key"),
        **_image_fields(),
    )

    with pytest.raises(ConfigError) as captured:
        recognize_provider_model_images(
            provider_model,
            (),
            prompt="Recognize this image.",
            timeout_seconds=0,
        )

    assert captured.value.code == "CONFIG_INVALID"
    assert ("google.genai" in sys.modules) is google_genai_was_loaded
    assert ("openai" in sys.modules) is openai_was_loaded


def test_provider_model_rejects_inconsistent_capabilities_and_retry_rules():
    with pytest.raises(ConfigError):
        ProviderModel(
            vendor="google",
            model="gemini-test-model",
            adapter_id="google_genai",
            settings=GoogleGenAISettings(),
            **_image_fields(
                supports_plain_ocr=False,
                supports_detail_ocr=True,
                default_image_batch_size=None,
            ),
        )

    with pytest.raises(ConfigError):
        ProviderModel(
            vendor="google",
            model="gemini-test-model",
            adapter_id="google_genai",
            settings=GoogleGenAISettings(),
            **_image_fields(
                retry_rules={"PROVIDER_TIMEOUT": ("current", -1, 1)}
            ),
        )


def test_batchify_images_uses_provider_default_and_explicit_size_wins(tmp_path):
    sources = tuple(
        write_test_image(tmp_path / f"page-{index}.png", color=(index, index, index))
        for index in range(3)
    )
    provider = ProviderModel(
        vendor="google",
        model="gemini-test-model",
        adapter_id="google_genai",
        settings=GoogleGenAISettings(),
        **_image_fields(default_image_batch_size=2),
    )

    assert batchify_images(sources, provider=provider) == (
        sources[:2],
        sources[2:],
    )
    assert batchify_images(sources, provider=provider, batch_size=3) == (sources,)


def test_batchify_images_uses_smallest_flat_provider_default(tmp_path):
    sources = tuple(
        write_test_image(tmp_path / f"page-{index}.png", color=(index, index, index))
        for index in range(3)
    )
    first = ProviderModel(
        vendor="google",
        model="gemini-test-a",
        adapter_id="google_genai",
        settings=GoogleGenAISettings(),
        **_image_fields(default_image_batch_size=3),
    )
    second = ProviderModel(
        vendor="google",
        model="gemini-test-b",
        adapter_id="google_genai",
        settings=GoogleGenAISettings(),
        **_image_fields(default_image_batch_size=2),
    )

    assert batchify_images(sources, provider=[first, second]) == (
        sources[:2],
        sources[2:],
    )
    assert batchify_images(
        sources,
        provider=[first, second],
        batch_size=3,
    ) == (sources,)

    duplicate_model = ProviderModel(
        vendor="google",
        model="gemini-test-a",
        adapter_id="google_genai",
        settings=GoogleGenAISettings(api_key="another-test-key"),
        **_image_fields(default_image_batch_size=1),
    )
    with pytest.raises(ConfigError) as captured:
        batchify_images(sources, provider=[first, duplicate_model])
    assert captured.value.details["provider_calls_attempted"] == 0


def test_batchify_images_flattens_defaults_but_preserves_nested_duplicates(
    tmp_path,
):
    sources = tuple(
        write_test_image(tmp_path / f"page-{index}.png", color=(index, index, index))
        for index in range(3)
    )
    first = ProviderModel(
        vendor="google",
        model="gemini-test-a",
        adapter_id="google_genai",
        settings=GoogleGenAISettings(),
        **_image_fields(default_image_batch_size=3),
    )
    second = ProviderModel(
        vendor="google",
        model="gemini-test-b",
        adapter_id="google_genai",
        settings=GoogleGenAISettings(),
        **_image_fields(default_image_batch_size=2),
    )
    same_model_other_lane = ProviderModel(
        vendor="google",
        model="gemini-test-a",
        adapter_id="google_genai",
        settings=GoogleGenAISettings(api_key="other-lane-key"),
        **_image_fields(default_image_batch_size=1),
    )

    assert batchify_images(sources, provider=[[first], [second]]) == (
        sources[:2],
        sources[2:],
    )
    assert batchify_images(
        sources,
        provider=[[first], [same_model_other_lane]],
    ) == tuple((source,) for source in sources)
