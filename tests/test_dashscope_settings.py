from dataclasses import FrozenInstanceError

import pytest

from ocrllm import (
    Config,
    DashScopeSettings,
    RecognitionPreferences,
    VisionModelSettings,
    recognize,
)
from ocrllm.errors import ConfigError


def test_dashscope_settings_for_region_derives_shared_endpoint():
    settings = DashScopeSettings.for_region("cn-beijing")

    assert settings.base_url == (
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )


def test_dashscope_settings_for_region_rejects_region_without_shared_endpoint():
    with pytest.raises(ConfigError):
        DashScopeSettings.for_region("ap-northeast-1")


@pytest.mark.parametrize(
    ("region", "base_url"),
    [
        (
            "cn-beijing",
            "https://llm-workspace1.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        ),
        (
            "ap-southeast-1",
            "https://llm-workspace1.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
        ),
        (
            "ap-southeast-1",
            "https://workspace1.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
        ),
        (
            "ap-northeast-1",
            "https://llm-workspace1.ap-northeast-1.maas.aliyuncs.com/compatible-mode/v1",
        ),
        (
            "eu-central-1",
            "https://llm-workspace1.eu-central-1.maas.aliyuncs.com/compatible-mode/v1",
        ),
        (
            "cn-hongkong",
            "https://llm-workspace1.cn-hongkong.maas.aliyuncs.com/compatible-mode/v1",
        ),
        (
            "cn-beijing",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        (
            "ap-southeast-1",
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        ),
        (
            "cn-hongkong",
            "https://cn-hongkong.dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        (
            "us-east-1",
            "https://dashscope-us.aliyuncs.com/compatible-mode/v1",
        ),
    ],
)
def test_dashscope_settings_accept_documented_region_endpoint_pairs(region, base_url):
    settings = DashScopeSettings(region=region, base_url=base_url)

    assert settings.region == region
    assert settings.base_url == base_url
    assert settings.api_key is None
    assert settings.enable_thinking is False
    assert settings.vl_high_resolution_images is True
    assert settings.standalone_sign_scout_model is None


@pytest.mark.parametrize("bad_value", ("", "qwen3.7-plus", 2, True, object()))
def test_dashscope_settings_reject_unsupported_sign_scout_models(bad_value):
    with pytest.raises(ConfigError, match="standalone_sign_scout_model"):
        DashScopeSettings(
            region="cn-beijing",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            standalone_sign_scout_model=bad_value,  # type: ignore[arg-type]
        )


def test_config_accepts_exact_sign_scout_only_with_default_workflow():
    settings = DashScopeSettings(
        region="cn-beijing",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        enable_thinking=True,
        standalone_sign_scout_model="qwen-vl-max",
    )

    config = Config(provider=settings)

    assert config.provider is not settings
    assert type(config.provider) is DashScopeSettings
    assert config.provider.standalone_sign_scout_model == "qwen-vl-max"

    with pytest.raises(ConfigError, match="default RecognitionPreferences"):
        Config(
            provider=settings,
            preferences=RecognitionPreferences(review_passes=1),
        )


def test_config_accepts_same_pinned_qwen37_primary_and_sign_scout():
    model = "qwen3.7-plus-2026-05-26"
    settings = DashScopeSettings(
        region="cn-beijing",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        enable_thinking=True,
        standalone_sign_scout_model=model,
    )

    config = Config(
        provider=settings,
        vision_model=VisionModelSettings(name=model),
    )

    assert config.vision_model.name == model
    assert type(config.provider) is DashScopeSettings
    assert config.provider.standalone_sign_scout_model == model


def test_dashscope_settings_are_frozen_slotted_and_require_explicit_routing():
    settings = _settings()

    assert not hasattr(settings, "__dict__")
    with pytest.raises(FrozenInstanceError):
        settings.region = "cn-beijing"  # type: ignore[misc]
    with pytest.raises(TypeError):
        DashScopeSettings()  # type: ignore[call-arg]


@pytest.mark.parametrize("field_name", ["enable_thinking", "vl_high_resolution_images"])
@pytest.mark.parametrize("bad_value", [0, 1, "false", None, object()])
def test_dashscope_settings_require_exact_booleans(field_name, bad_value):
    with pytest.raises(ConfigError, match=field_name) as caught:
        DashScopeSettings(
            region="ap-southeast-1",
            base_url=(
                "https://llm-workspace1.ap-southeast-1.maas.aliyuncs.com/"
                "compatible-mode/v1"
            ),
            **{field_name: bad_value},
        )

    assert caught.value.code == "CONFIG_INVALID"


@pytest.mark.parametrize(
    ("region", "base_url"),
    [
        ("unknown-1", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        ("cn-beijing", "http://dashscope.aliyuncs.com/compatible-mode/v1"),
        ("cn-beijing", "https://example.com/compatible-mode/v1"),
        (
            "cn-beijing",
            "https://dashscope.aliyuncs.com.evil.example/compatible-mode/v1",
        ),
        (
            "cn-beijing",
            "https://user:secret@dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        ("cn-beijing", "https://dashscope.aliyuncs.com:443/compatible-mode/v1"),
        ("cn-beijing", "https://dashscope.aliyuncs.com/api/v1"),
        ("cn-beijing", "https://dashscope.aliyuncs.com/compatible-mode/v1/"),
        ("cn-beijing", "https://dashscope.aliyuncs.com/compatible-mode/v1?x=1"),
        ("cn-beijing", "https://dashscope.aliyuncs.com/compatible-mode/v1?"),
        ("cn-beijing", "https://dashscope.aliyuncs.com/compatible-mode/v1#x"),
        ("cn-beijing", "https://dashscope.aliyuncs.com/compatible-mode/v1#"),
        (
            "cn-beijing",
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        ),
        (
            "cn-beijing",
            "https://llm-workspace1.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
        ),
        (
            "ap-southeast-1",
            "https://-workspace.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
        ),
        (
            "us-east-1",
            "https://llm-workspace1.us-east-1.maas.aliyuncs.com/compatible-mode/v1",
        ),
        ("cn-beijing", "https://DASHSCOPE.aliyuncs.com/compatible-mode/v1"),
        ("cn-beijing", "https://dashscope.\naliyuncs.com/compatible-mode/v1"),
    ],
)
def test_dashscope_settings_reject_unapproved_or_mismatched_endpoints(region, base_url):
    with pytest.raises(ConfigError) as caught:
        DashScopeSettings(region=region, base_url=base_url)

    assert caught.value.code == "CONFIG_INVALID"
    assert "secret" not in str(caught.value)


def test_dashscope_settings_reject_string_subclasses():
    class TextSubclass(str):
        def __hash__(self):
            raise RuntimeError("HOSTILE_DASHSCOPE_HASH_SECRET")

    with pytest.raises(ConfigError, match="region"):
        DashScopeSettings(
            region=TextSubclass("cn-beijing"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    with pytest.raises(ConfigError, match="base_url"):
        DashScopeSettings(
            region="cn-beijing",
            base_url=TextSubclass(
                "https://dashscope.aliyuncs.com/compatible-mode/v1"
            ),
        )
    with pytest.raises(ConfigError, match="standalone_sign_scout_model") as captured:
        DashScopeSettings(
            region="cn-beijing",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            standalone_sign_scout_model=TextSubclass("qwen-vl-max"),
        )
    assert "HOSTILE_DASHSCOPE_HASH_SECRET" not in str(captured.value)


def test_config_uses_exact_dashscope_settings_to_select_builtin_adapter():
    settings = _settings()

    config = Config(provider=settings)
    assert config.provider == settings
    assert config.provider is not settings

    with pytest.raises(ConfigError, match="string provider categories"):
        Config(provider="dashscope")

def test_config_rejects_dashscope_settings_subclass_and_string_subclass():
    class SettingsSubclass(DashScopeSettings):
        pass

    class DashScopeName(str):
        pass

    settings = _settings()
    with pytest.raises(ConfigError, match="exact DashScopeSettings"):
        Config(
            provider=SettingsSubclass(
                region=settings.region,
                base_url=settings.base_url,
            )
        )
    with pytest.raises(ConfigError, match="string provider categories"):
        Config(provider=DashScopeName("dashscope"))


def test_config_omits_composed_dashscope_settings_from_repr():
    sentinel = "llm-reprsentinel391"
    settings = DashScopeSettings(
        region="ap-southeast-1",
        base_url=(
            f"https://{sentinel}.ap-southeast-1.maas.aliyuncs.com/"
            "compatible-mode/v1"
        ),
    )

    rendered = repr(Config(provider=settings))

    assert sentinel not in rendered
    assert "provider=" not in rendered


def test_dashscope_api_key_is_secret_and_validated_without_echo():
    sentinel = "api-secret-sentinel-337"
    settings = DashScopeSettings(
        region="cn-beijing",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=sentinel,
    )

    assert settings.api_key == sentinel
    assert sentinel not in repr(settings)
    assert sentinel not in repr(Config(provider=settings))

    for bad_value in ("", " padded ", "sk-sp-DO_NOT_ECHO", 1, True):
        with pytest.raises(ConfigError) as captured:
            DashScopeSettings(
                region="cn-beijing",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key=bad_value,  # type: ignore[arg-type]
            )
        if bad_value:
            assert str(bad_value) not in str(captured.value)


def test_config_copies_and_revalidates_mutated_dashscope_settings():
    settings = _settings()
    config = Config(provider=settings)

    object.__setattr__(
        settings,
        "base_url",
        "https://example.invalid/compatible-mode/v1",
    )

    assert type(config.provider) is DashScopeSettings
    assert config.provider.base_url != settings.base_url
    with pytest.raises(ConfigError):
        Config(provider=settings)


def test_public_call_revalidates_a_mutated_nested_endpoint_before_source_work(tmp_path):
    config = Config(provider=_settings())
    assert type(config.provider) is DashScopeSettings
    object.__setattr__(
        config.provider,
        "base_url",
        "https://example.invalid/compatible-mode/v1",
    )

    with pytest.raises(ConfigError) as captured:
        recognize(tmp_path / "missing.png", config=config)

    assert captured.value.code == "CONFIG_INVALID"


def _settings() -> DashScopeSettings:
    return DashScopeSettings(
        region="ap-southeast-1",
        base_url=(
            "https://llm-workspace1.ap-southeast-1.maas.aliyuncs.com/"
            "compatible-mode/v1"
        ),
    )
