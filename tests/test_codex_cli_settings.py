from dataclasses import FrozenInstanceError

import pytest

from ocrllm import CodexCLISettings, Config, VisionModelSettings
from ocrllm.errors import ConfigError
from ocrllm.providers.codex_cli.provider_settings import (
    DEFAULT_CODEX_CLI_MAX_IMAGES_PER_CALL,
    DEFAULT_CODEX_CLI_MODEL,
    DEFAULT_CODEX_CLI_REASONING_EFFORT,
    resolve_codex_cli_model,
)
from ocrllm.providers.resolve_vision_provider import resolve_vision_provider


def test_codex_cli_settings_defaults_target_luna_light_batch_8():
    settings = CodexCLISettings()

    assert settings.command == "codex"
    assert settings.model == "gpt-5.6-luna"
    assert settings.reasoning_effort == "low"
    assert settings.fast_mode is False
    assert settings.timeout_seconds == 1800.0
    assert type(settings.timeout_seconds) is float
    assert settings.max_images_per_call == 8
    assert DEFAULT_CODEX_CLI_MODEL == "gpt-5.6-luna"
    assert DEFAULT_CODEX_CLI_REASONING_EFFORT == "low"
    assert DEFAULT_CODEX_CLI_MAX_IMAGES_PER_CALL == 8


def test_codex_cli_settings_are_frozen_slotted_with_defaults():
    settings = CodexCLISettings()

    assert not hasattr(settings, "__dict__")
    with pytest.raises(FrozenInstanceError):
        settings.model = "gpt-5.6-sol"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("command", ""),
        ("command", "  codex  "),
        ("command", "cod\nex"),
        ("command", 1),
        ("model", ""),
        ("model", " gpt-5.6-luna"),
        ("model", "gpt 5.6 luna"),
        ("model", True),
        ("reasoning_effort", ""),
        ("reasoning_effort", "lo w"),
        ("reasoning_effort", None),
        ("service_tier", "bad tier"),
        ("service_tier", 1),
        ("usage_event_dir", "relative/path"),
        ("usage_event_dir", ""),
        ("course_validation", 1),
        ("adjacent_repeat_limit", 2),
        ("adjacent_repeat_limit", True),
        ("fast_mode", 0),
        ("fast_mode", "yes"),
        ("timeout_seconds", 0),
        ("timeout_seconds", -1),
        ("timeout_seconds", float("inf")),
        ("timeout_seconds", 7201),
        ("timeout_seconds", True),
        ("timeout_seconds", "1800"),
        ("max_images_per_call", 0),
        ("max_images_per_call", 11),
        ("max_images_per_call", 8.0),
        ("max_images_per_call", True),
    ],
)
def test_codex_cli_settings_reject_invalid_fields(field_name, bad_value):
    with pytest.raises(ConfigError, match=field_name) as caught:
        CodexCLISettings(**{field_name: bad_value})

    assert caught.value.code == "CONFIG_INVALID"


def test_codex_cli_settings_reject_string_subclasses():
    class TextSubclass(str):
        def __hash__(self):
            raise RuntimeError("HOSTILE_CODEX_HASH_SECRET")

    with pytest.raises(ConfigError, match="model") as captured:
        CodexCLISettings(model=TextSubclass("gpt-5.6-luna"))
    assert "HOSTILE_CODEX_HASH_SECRET" not in str(captured.value)


def test_config_copies_and_revalidates_codex_cli_settings():
    settings = CodexCLISettings(model="gpt-5.6-sol")

    config = Config(provider=settings)

    assert config.provider == settings
    assert config.provider is not settings
    assert type(config.provider) is CodexCLISettings

    object.__setattr__(settings, "model", "bad model")
    assert config.provider.model == "gpt-5.6-sol"
    with pytest.raises(ConfigError):
        Config(provider=settings)


def test_config_rejects_codex_cli_settings_subclass():
    class SettingsSubclass(CodexCLISettings):
        pass

    with pytest.raises(ConfigError, match="exact CodexCLISettings"):
        Config(provider=SettingsSubclass())


def test_resolve_codex_cli_model_prefers_caller_pinned_name():
    settings = CodexCLISettings()

    assert resolve_codex_cli_model(None, settings) == "gpt-5.6-luna"
    assert resolve_codex_cli_model("gpt-5.6-sol", settings) == "gpt-5.6-sol"


def test_resolve_vision_provider_selects_codex_cli_builtin():
    resolved = resolve_vision_provider(Config(provider=CodexCLISettings()))

    assert resolved.name == "codex_cli"
    assert resolved.built_in is True
    assert resolved.model == "gpt-5.6-luna"
    assert callable(resolved.value.recognize_images)


def test_resolve_vision_provider_lets_vision_model_name_override_codex_model():
    config = Config(
        provider=CodexCLISettings(),
        vision_model=VisionModelSettings(name="gpt-5.6-sol"),
    )

    resolved = resolve_vision_provider(config)

    assert resolved.name == "codex_cli"
    assert resolved.model == "gpt-5.6-sol"


def test_codex_new_opt_ins_survive_config_copy(tmp_path):
    settings = CodexCLISettings(service_tier="default", usage_event_dir=tmp_path,
        course_validation=True, adjacent_repeat_limit=8)
    copied = Config(provider=settings).provider
    assert copied == settings and copied is not settings
    assert copied.service_tier == "default" and copied.usage_event_dir == tmp_path
    assert copied.course_validation and copied.adjacent_repeat_limit == 8


def test_explicit_tier_conflict_rejected_without_changing_legacy_fast_mode():
    with pytest.raises(ConfigError, match="conflicts"):
        CodexCLISettings(service_tier="default", fast_mode=True)
    assert CodexCLISettings(service_tier="priority", fast_mode=True).fast_mode
