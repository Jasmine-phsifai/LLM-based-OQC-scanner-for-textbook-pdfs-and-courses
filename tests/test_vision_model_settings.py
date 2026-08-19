from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from ocrllm import (
    Config,
    DashScopeSettings,
    RecognitionExecutionPolicy,
    VisionModelSettings,
    recognize,
)
from ocrllm.errors import ConfigError, InvalidSource
from ocrllm.providers.dashscope.resolve_dashscope_maximum_images import (
    resolve_dashscope_maximum_images,
)
from ocrllm.providers.dashscope.resolve_dashscope_model import (
    DEFAULT_DASHSCOPE_MODEL,
)
from write_test_image import write_test_image


class CountingProvider:
    def __init__(self) -> None:
        self.calls = 0

    def recognize_images(self, image_paths, *, prompt, config):
        self.calls += 1
        return "# Unexpected provider call\n"


class HostileText(str):
    def strip(self, *args, **kwargs):
        raise RuntimeError("HOSTILE_MODEL_STRIP_SECRET")

    def __iter__(self):
        raise RuntimeError("HOSTILE_MODEL_ITER_SECRET")


def test_vision_model_settings_are_exact_frozen_and_bounded() -> None:
    settings = VisionModelSettings(
        name="qwen3.7-plus-2026-05-26",
        maximum_images_per_request=3,
    )

    assert settings.name == "qwen3.7-plus-2026-05-26"
    assert settings.maximum_images_per_request == 3
    assert not hasattr(settings, "__dict__")
    with pytest.raises(FrozenInstanceError):
        settings.name = "another"  # type: ignore[misc]


@pytest.mark.parametrize("bad_name", ["", " padded ", "line\nbreak", 1, True])
def test_vision_model_settings_reject_invalid_names(bad_name) -> None:
    with pytest.raises(ConfigError, match="VisionModelSettings.name"):
        VisionModelSettings(name=bad_name)  # type: ignore[arg-type]


def test_vision_model_settings_reject_string_subclass_without_overrides() -> None:
    with pytest.raises(ConfigError) as captured:
        VisionModelSettings(name=HostileText("model"))

    rendered = f"{captured.value!s} {captured.value!r}"
    assert "HOSTILE_MODEL_STRIP_SECRET" not in rendered
    assert "HOSTILE_MODEL_ITER_SECRET" not in rendered


@pytest.mark.parametrize("bad_limit", [True, 0, 11, 1.0, "1"])
def test_vision_model_settings_reject_invalid_image_limits(bad_limit) -> None:
    with pytest.raises(ConfigError, match="maximum_images_per_request"):
        VisionModelSettings(
            maximum_images_per_request=bad_limit  # type: ignore[arg-type]
        )


def test_config_copies_and_revalidates_exact_vision_model_settings() -> None:
    settings = VisionModelSettings(name="qwen-vl-max", maximum_images_per_request=2)

    config = Config(vision_model=settings)

    assert config.vision_model == settings
    assert config.vision_model is not settings

    object.__setattr__(settings, "maximum_images_per_request", 0)
    assert config.vision_model.maximum_images_per_request == 2
    with pytest.raises(ConfigError, match="maximum_images_per_request"):
        Config(vision_model=settings)


def test_config_rejects_vision_model_settings_subclass() -> None:
    class SettingsSubclass(VisionModelSettings):
        pass

    with pytest.raises(ConfigError, match="exact VisionModelSettings"):
        Config(vision_model=SettingsSubclass())


def test_model_limit_rejects_group_before_file_or_provider_access(tmp_path) -> None:
    provider = CountingProvider()
    config = Config(
        provider=provider,
        vision_model=VisionModelSettings(maximum_images_per_request=1),
    )

    with pytest.raises(InvalidSource) as captured:
        recognize(
            (tmp_path / "missing-1.png", tmp_path / "missing-2.png"),
            config=config,
        )

    assert captured.value.code == "SOURCE_TOO_LARGE"
    assert captured.value.details == {
        "image_count": 2,
        "maximum_image_count": 1,
        "limit_source": "vision_model_settings",
    }
    assert provider.calls == 0


def test_execution_limit_wins_when_stricter_than_model_limit(tmp_path) -> None:
    provider = CountingProvider()
    config = Config(
        provider=provider,
        vision_model=VisionModelSettings(maximum_images_per_request=3),
        execution=RecognitionExecutionPolicy(maximum_images_per_request=2),
    )

    with pytest.raises(InvalidSource) as captured:
        recognize(
            tuple(tmp_path / f"missing-{index}.png" for index in range(3)),
            config=config,
        )

    assert captured.value.details["maximum_image_count"] == 2
    assert captured.value.details["limit_source"] == "recognition_execution_policy"
    assert provider.calls == 0


def test_unavailable_builtin_model_is_reported_by_provider_catalog(tmp_path, monkeypatch) -> None:
    resolver = __import__(
        "ocrllm.providers.dashscope.resolve_dashscope_model",
        fromlist=["fetch_dashscope_model_catalog"],
    )
    monkeypatch.setattr(resolver, "fetch_dashscope_model_catalog", lambda settings: frozenset())
    source = write_test_image(tmp_path / "board.png")
    config = Config(
        provider=DashScopeSettings(
            region="cn-beijing",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key="test-key",
        ),
        vision_model=VisionModelSettings(name="unsupported-model"),
    )

    with pytest.raises(ConfigError, match="DashScope does not serve") as captured:
        recognize(source, config=config)

    assert captured.value.code == "CONFIG_INVALID"


def test_dashscope_model_capability_is_explicit_for_every_supported_model() -> None:
    assert resolve_dashscope_maximum_images(DEFAULT_DASHSCOPE_MODEL) == 10
    assert resolve_dashscope_maximum_images("qwen3.7-plus") == 10
    assert resolve_dashscope_maximum_images("qwen-vl-max") == 10

    assert resolve_dashscope_maximum_images("unknown") == 10
