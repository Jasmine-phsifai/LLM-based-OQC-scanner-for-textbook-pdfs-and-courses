"""Offline contract for the public provider-model planning slice."""

from __future__ import annotations

import dataclasses
import sys
from types import ModuleType, SimpleNamespace

import pytest

from ocrllm import OpenAICompatibleSettings, batchify_images
from ocrllm.errors import ConfigError, InvalidSource, ProviderError
from ocrllm.providers.dashscope.provider_settings import DashScopeSettings
from ocrllm.providers.google_genai.provider_settings import GoogleGenAISettings
from ocrllm.providers.provider_model import ProviderModel
from ocrllm.providers.provider_model_presets import (
    DASHSCOPE_QWEN3_5_OCR_CN_BEIJING,
    DASHSCOPE_QWEN3_5_OCR_OPENAI_COMPATIBLE_CN_BEIJING,
    GOOGLE_GEMINI_2_5_FLASH,
    GOOGLE_GEMINI_2_5_FLASH_OPENAI_COMPATIBLE,
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

    assert GOOGLE_GEMINI_2_5_FLASH_OPENAI_COMPATIBLE == ProviderModel(
        vendor="google",
        model="gemini-2.5-flash",
        adapter_id="openai_compatible_chat",
        settings=OpenAICompatibleSettings(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key_env="GEMINI_API_KEY",
            api_key="test-only-google-key",
        ),
        **_image_fields(default_image_batch_size=2),
    )
    assert GOOGLE_GEMINI_2_5_FLASH_OPENAI_COMPATIBLE.settings.api_key is None
    assert GOOGLE_GEMINI_2_5_FLASH_OPENAI_COMPATIBLE.supports_audio is False

    assert (
        DASHSCOPE_QWEN3_5_OCR_OPENAI_COMPATIBLE_CN_BEIJING
        == ProviderModel(
            vendor="dashscope",
            model="qwen3.5-ocr",
            adapter_id="openai_compatible_chat",
            settings=OpenAICompatibleSettings(
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key_env="DASHSCOPE_API_KEY",
                api_key="test-only-dashscope-key",
            ),
            **_image_fields(default_image_batch_size=2),
        )
    )
    assert (
        DASHSCOPE_QWEN3_5_OCR_OPENAI_COMPATIBLE_CN_BEIJING.settings.api_key
        is None
    )


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


def test_openai_compatible_settings_are_public_exact_and_secret_safe():
    secret = "test-only-compatible-secret"
    settings = OpenAICompatibleSettings(
        base_url="http://127.0.0.1:8000/v1",
        api_key_env="LOCAL_LLM_KEY",
        api_key=secret,
    )

    assert settings.base_url == "http://127.0.0.1:8000/v1"
    assert settings.api_key_env == "LOCAL_LLM_KEY"
    assert settings.api_key == secret
    assert secret not in repr(settings)

    for kwargs in (
        {"base_url": "relative/v1", "api_key_env": "LOCAL_LLM_KEY"},
        {"base_url": "https://user@example.test/v1", "api_key_env": "KEY"},
        {"base_url": "https://example.test/v1", "api_key_env": "bad-name"},
    ):
        with pytest.raises(ConfigError):
            OpenAICompatibleSettings(**kwargs)


def test_openai_compatible_image_route_uses_standard_minimal_request(
    tmp_path,
    monkeypatch,
):
    sources = (
        write_test_image(tmp_path / "first.png", color=(1, 2, 3)),
        write_test_image(tmp_path / "second.png", color=(4, 5, 6)),
    )
    captured = {}
    response = _compatible_response(markdown="Recognized board", model="served-alias")
    monkeypatch.setitem(
        sys.modules,
        "openai",
        _fake_openai_module(response=response, captured=captured),
    )
    provider = _compatible_provider(api_key="test-only-key")

    result = recognize_provider_model_images(
        provider,
        sources,
        prompt="Recognize both images in order.",
        timeout_seconds=7,
    )

    assert result.markdown == "Recognized board"
    assert result.input_tokens == 123
    assert result.output_tokens == 45
    assert result.client_closed is True
    assert captured["client"] == {
        "api_key": "test-only-key",
        "base_url": "https://example.test/v1",
        "timeout": 7.0,
        "max_retries": 0,
    }
    request = captured["request"]
    assert set(request) == {"model", "messages"}
    assert request["model"] == "compatible-test-model"
    content = request["messages"][0]["content"]
    assert [item["type"] for item in content] == [
        "image_url",
        "image_url",
        "text",
    ]
    assert all(
        item["image_url"]["url"].startswith("data:image/png;base64,")
        for item in content[:2]
    )
    assert content[-1]["text"] == "Recognize both images in order."
    assert captured["closed"] is True


def test_openai_compatible_http_200_without_text_is_failure_with_usage(
    tmp_path,
    monkeypatch,
):
    source = write_test_image(tmp_path / "source.png", color=(1, 2, 3))
    captured = {}
    monkeypatch.setitem(
        sys.modules,
        "openai",
        _fake_openai_module(
            response=_compatible_response(markdown=None),
            captured=captured,
        ),
    )

    with pytest.raises(ProviderError) as caught:
        recognize_provider_model_images(
            _compatible_provider(api_key="test-only-key"),
            (source,),
            prompt="Recognize this image.",
        )

    assert caught.value.code == "PROVIDER_RESPONSE_INVALID"
    assert caught.value.details["reason"] == "missing_text"
    assert caught.value.details["input_tokens"] == 123
    assert caught.value.details["output_tokens"] == 45
    assert caught.value.details["provider_calls_attempted"] == 1
    assert captured["closed"] is True


def test_openai_compatible_preserves_success_when_client_close_fails(
    tmp_path,
    monkeypatch,
):
    source = write_test_image(tmp_path / "source.png", color=(1, 2, 3))
    captured = {}
    monkeypatch.setitem(
        sys.modules,
        "openai",
        _fake_openai_module(
            response=_compatible_response(),
            captured=captured,
            close_fails=True,
        ),
    )

    result = recognize_provider_model_images(
        _compatible_provider(api_key="test-only-key"),
        (source,),
        prompt="Recognize this image.",
    )

    assert result.markdown == "Recognized"
    assert result.client_closed is False


def test_openai_compatible_local_preflight_is_zero_call_and_sdk_lazy(
    tmp_path,
    monkeypatch,
):
    captured = {}
    monkeypatch.setitem(
        sys.modules,
        "openai",
        _fake_openai_module(response=None, captured=captured),
    )

    with pytest.raises(InvalidSource) as caught:
        recognize_provider_model_images(
            _compatible_provider(api_key="test-only-key"),
            (tmp_path / "missing.png",),
            prompt="Recognize this image.",
        )

    assert caught.value.code == "SOURCE_NOT_FOUND"
    assert caught.value.details["provider_calls_attempted"] == 0
    assert captured == {}


def test_openai_compatible_authentication_error_is_canonical_and_redacted(
    tmp_path,
    monkeypatch,
):
    source = write_test_image(tmp_path / "source.png", color=(1, 2, 3))
    captured = {}
    module = _fake_openai_module(
        error=_FakeAuthenticationError(),
        captured=captured,
    )
    monkeypatch.setitem(sys.modules, "openai", module)

    with pytest.raises(ProviderError) as caught:
        recognize_provider_model_images(
            _compatible_provider(api_key="test-only-key"),
            (source,),
            prompt="Recognize this image.",
        )

    assert caught.value.code == "PROVIDER_AUTHENTICATION"
    assert caught.value.details["http_status"] == 401
    assert caught.value.details["provider_code"] == "AuthenticationError"
    assert caught.value.details["provider_calls_attempted"] == 1
    assert "private" not in str(caught.value)
    assert captured["closed"] is True

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


def _compatible_provider(*, api_key: str | None) -> ProviderModel:
    return ProviderModel(
        vendor="test-vendor",
        model="compatible-test-model",
        adapter_id="openai_compatible_chat",
        settings=OpenAICompatibleSettings(
            base_url="https://example.test/v1",
            api_key_env="TEST_COMPATIBLE_KEY",
            api_key=api_key,
        ),
        **_image_fields(),
    )


def _compatible_response(*, markdown="Recognized", model="compatible-test-model"):
    return SimpleNamespace(
        model=model,
        choices=[
            SimpleNamespace(
                index=0,
                finish_reason="stop",
                message=SimpleNamespace(
                    role="assistant",
                    content=markdown,
                    refusal=None,
                ),
            )
        ],
        usage=SimpleNamespace(prompt_tokens=123, completion_tokens=45),
    )


class _FakeAuthenticationError(Exception):
    status_code = 401
    code = "AuthenticationError"
    request_id = "request-test"

    def __str__(self):
        return "private provider text"


def _fake_openai_module(
    *,
    captured,
    response=None,
    error=None,
    close_fails=False,
):
    module = ModuleType("openai")
    module.__version__ = "2.30.0"
    module.AuthenticationError = _FakeAuthenticationError

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            captured["closed"] = False
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=self.create)
            )

        def create(self, **kwargs):
            captured["request"] = kwargs
            if error is not None:
                raise error
            return response

        def close(self):
            if close_fails:
                raise OSError("private close failure")
            captured["closed"] = True

    module.OpenAI = FakeClient
    return module
