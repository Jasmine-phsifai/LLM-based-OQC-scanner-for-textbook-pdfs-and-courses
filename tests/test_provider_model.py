"""Offline contract for the first private provider-model runtime slice."""

from __future__ import annotations

import dataclasses
import sys

import pytest

from ocrllm.errors import ConfigError, InvalidSource
from ocrllm.providers.dashscope.provider_settings import DashScopeSettings
from ocrllm.providers.google_genai.provider_settings import GoogleGenAISettings
from ocrllm.providers.provider_model import ProviderModel
from ocrllm.providers.recognize_provider_model_images import (
    recognize_provider_model_images,
)


def test_provider_model_identity_is_immutable_and_secret_safe():
    first_secret = "test-only-google-key-a"
    second_secret = "test-only-google-key-b"
    first = ProviderModel(
        vendor="google",
        model="gemini-test-model",
        adapter_id="google_genai",
        settings=GoogleGenAISettings(api_key=first_secret),
    )
    second = ProviderModel(
        vendor="google",
        model="gemini-test-model",
        adapter_id="google_genai",
        settings=GoogleGenAISettings(api_key=second_secret),
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


@pytest.mark.parametrize(
    "kwargs",
    (
        {
            "vendor": "google",
            "model": "gemini-test-model",
            "adapter_id": "google_genai",
            "settings": DashScopeSettings.for_region("cn-beijing"),
        },
        {
            "vendor": "google",
            "model": "gemini-test-model",
            "adapter_id": "unknown",
            "settings": GoogleGenAISettings(),
        },
        {
            "vendor": "google ",
            "model": "gemini-test-model",
            "adapter_id": "google_genai",
            "settings": GoogleGenAISettings(),
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
    provider_model = ProviderModel(
        vendor="google",
        model="gemini-test-model",
        adapter_id="google_genai",
        settings=GoogleGenAISettings(api_key="test-only-google-key"),
    )

    with pytest.raises(InvalidSource) as captured:
        recognize_provider_model_images(
            provider_model,
            (tmp_path / "missing.png",),
            prompt="Recognize this image.",
        )

    assert captured.value.code == "SOURCE_NOT_FOUND"
    assert captured.value.details["provider_calls_attempted"] == 0
    assert "google.genai" not in sys.modules
    assert "openai" not in sys.modules


def test_provider_model_image_consumer_validates_request_timeout_before_dispatch():
    provider_model = ProviderModel(
        vendor="google",
        model="gemini-test-model",
        adapter_id="google_genai",
        settings=GoogleGenAISettings(api_key="test-only-google-key"),
    )

    with pytest.raises(ConfigError) as captured:
        recognize_provider_model_images(
            provider_model,
            (),
            prompt="Recognize this image.",
            timeout_seconds=0,
        )

    assert captured.value.code == "CONFIG_INVALID"
    assert "google.genai" not in sys.modules
    assert "openai" not in sys.modules
