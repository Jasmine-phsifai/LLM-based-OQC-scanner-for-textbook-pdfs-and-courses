from dataclasses import FrozenInstanceError

import pytest

from ocrllm import RecognitionPreferences, VisionModelSettings
from ocrllm.config import Config
from ocrllm.errors import ConfigError


class SecretProvider:
    def __init__(self, secret: str) -> None:
        self.secret = secret

    def __repr__(self) -> str:
        return f"SecretProvider({self.secret})"


class SecretObject:
    def __init__(self, secret: str) -> None:
        self.secret = secret

    def __repr__(self) -> str:
        return self.secret


class HostileText(str):
    def strip(self, *args, **kwargs):
        raise RuntimeError("HOSTILE_CONFIG_TEXT_SECRET_9b31")

    def __hash__(self):
        raise RuntimeError("HOSTILE_CONFIG_HASH_SECRET_6e20")


def test_config_is_frozen_slotted_and_omits_secrets_from_repr(tmp_path):
    provider_secret = "PROVIDER-SECRET-7f391"
    api_secret = "API-SECRET-a512c"
    password_secret = "PDF-SECRET-b883d"
    extra_secret = "EXTRA-SECRET-c194e"

    config = Config(
        provider=SecretProvider(provider_secret + api_secret),
        pdf_password=password_secret,
        output_dir=tmp_path,
        extra={"provider_token": extra_secret},
    )

    rendered = repr(config)
    for sentinel in (provider_secret, api_secret, password_secret, extra_secret):
        assert sentinel not in rendered
    assert not hasattr(config, "__dict__")
    with pytest.raises(FrozenInstanceError):
        config.vision_model = VisionModelSettings(  # type: ignore[misc]
            name="another-model"
        )


def test_config_omits_cancellation_object_from_repr():
    sentinel = "CANCELLATION_OBJECT_SECRET_a461"

    rendered = repr(Config(cancellation=SecretObject(sentinel)))

    assert sentinel not in rendered


def test_config_does_not_expose_unimplemented_progress_hook():
    assert not hasattr(Config(), "progress")
    with pytest.raises(TypeError):
        Config(progress=object())  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"provider": HostileText("dashscope")},
        {"vision_model": object()},
        {"profile": HostileText("board")},
        {"pdf_password": HostileText("password")},
        {"input_languages": (HostileText("en"),)},
        {"output_language": HostileText("en")},
        {"output_dir": HostileText("output")},
    ],
)
def test_config_rejects_string_subclasses_without_running_overrides(kwargs):
    with pytest.raises(ConfigError) as captured:
        Config(**kwargs)

    rendered = f"{captured.value!s} {captured.value!r}"
    assert "HOSTILE_CONFIG_TEXT_SECRET_9b31" not in rendered
    assert "HOSTILE_CONFIG_HASH_SECRET_6e20" not in rendered


def test_config_copies_and_recursively_freezes_extra():
    original = {"nested": {"items": [1, {"enabled": True}]}}

    config = Config(extra=original)
    original["nested"]["items"].append(2)  # type: ignore[index,union-attr]

    nested = config.extra["nested"]
    assert nested["items"] == (1, {"enabled": True})  # type: ignore[index]
    with pytest.raises(TypeError):
        nested["new"] = "value"  # type: ignore[index]
    with pytest.raises(TypeError):
        nested["items"][1]["enabled"] = False  # type: ignore[index]


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), object()])
def test_config_rejects_non_json_or_nonfinite_extra_without_echoing_values(bad_value):
    extra_secret = "EXTRA-ERROR-SECRET-57ab9"

    with pytest.raises(ConfigError) as caught:
        Config(extra={"provider_token": extra_secret, "bad": bad_value})

    assert caught.value.code == "CONFIG_INVALID"
    assert extra_secret not in str(caught.value)
    assert extra_secret not in repr(caught.value)


def test_config_validation_error_does_not_render_other_secret_fields():
    secrets = (
        "PROVIDER-ERROR-SECRET-11",
        "PASSWORD-ERROR-SECRET-33",
        "EXTRA-ERROR-SECRET-44",
    )

    with pytest.raises(ConfigError) as caught:
        Config(
            provider=SecretProvider(secrets[0]),
            pdf_password=secrets[1],
            extra={"provider_token": secrets[2]},
            timeout_seconds=0,
        )

    rendered = f"{caught.value!s} {caught.value!r}"
    assert all(secret not in rendered for secret in secrets)


def test_config_normalizes_ordered_language_and_page_sequences():
    config = Config(
        input_languages=["en-US", "zh-CN"],  # type: ignore[arg-type]
        output_language="en",
        pdf_pages=[3, 1, 2],  # type: ignore[arg-type]
        timeout_seconds=30,
    )

    assert config.input_languages == ("en-US", "zh-CN")
    assert config.output_language == "en"
    assert config.pdf_pages == (3, 1, 2)
    assert config.timeout_seconds == 30.0


@pytest.mark.parametrize("bad_timeout", [True, 0, -1, 600.1, float("nan"), float("inf"), "30"])
def test_config_rejects_invalid_timeout(bad_timeout):
    with pytest.raises(ConfigError, match="timeout_seconds"):
        Config(timeout_seconds=bad_timeout)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"input_languages": ["en US"]},
        {"input_languages": ["en", "EN"]},
        {"output_language": "-en"},
        {"pdf_pages": []},
        {"pdf_pages": [0]},
        {"pdf_pages": [True]},
        {"pdf_pages": [1, 1]},
    ],
)
def test_config_rejects_invalid_language_and_page_values(kwargs):
    with pytest.raises(ConfigError):
        Config(**kwargs)


def test_resume_requires_output_and_conflicts_with_overwrite(tmp_path):
    with pytest.raises(ConfigError, match="requires Config.output_dir"):
        Config(resume=True)
    with pytest.raises(ConfigError, match="cannot both be true"):
        Config(resume=True, overwrite=True, output_dir=tmp_path)


def test_config_does_not_require_future_modality_fields_at_construction():
    config = Config(pdf_pages=(2,), profile="future-profile")

    assert config.pdf_pages == (2,)
    assert config.pdf_mode is None
    assert config.provider is None


def test_output_directory_preserves_memory_only_default_and_converts_paths(tmp_path):
    assert Config().output_directory() is None
    assert Config(output_dir=str(tmp_path)).output_directory() == tmp_path


def test_recognition_preferences_are_exact_frozen_and_bounded():
    assert Config().preferences == RecognitionPreferences(
        draft_candidates=1,
        review_passes=0,
    )
    assert Config(
        preferences=RecognitionPreferences(review_passes=1)
    ).preferences.review_passes == 1
    consensus = Config(
        preferences=RecognitionPreferences(draft_candidates=2, review_passes=1)
    ).preferences
    assert consensus.draft_candidates == 2
    assert consensus.review_passes == 1

    for bad_value in (True, -1, 2, "1"):
        with pytest.raises(ConfigError, match="review_passes"):
            RecognitionPreferences(review_passes=bad_value)  # type: ignore[arg-type]

    for bad_value in (True, 0, 3, "2"):
        with pytest.raises(ConfigError, match="draft_candidates"):
            RecognitionPreferences(draft_candidates=bad_value)  # type: ignore[arg-type]

    with pytest.raises(ConfigError, match="requires review_passes=1"):
        RecognitionPreferences(draft_candidates=2)

    class PreferencesSubclass(RecognitionPreferences):
        pass

    with pytest.raises(ConfigError, match="exact RecognitionPreferences"):
        Config(preferences=PreferencesSubclass())


def test_config_revalidates_mutated_nested_preferences():
    preferences = RecognitionPreferences(review_passes=0)
    object.__setattr__(preferences, "review_passes", 2)

    with pytest.raises(ConfigError, match="review_passes"):
        Config(preferences=preferences)


def test_config_revalidates_mutated_draft_candidate_count():
    preferences = RecognitionPreferences()
    object.__setattr__(preferences, "draft_candidates", 2)

    with pytest.raises(ConfigError, match="requires review_passes=1"):
        Config(preferences=preferences)
