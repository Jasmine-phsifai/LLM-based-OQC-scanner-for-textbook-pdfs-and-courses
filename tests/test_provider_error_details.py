from pathlib import Path

import pytest

from ocrllm import Config, ProviderError, recognize
from ocrllm.providers.call_vision_provider import call_vision_provider
from ocrllm.providers.resolved_vision_provider import ResolvedVisionProvider

from write_test_image import write_test_image


class _ResponseProvider:
    def __init__(self, response: str) -> None:
        self.response = response

    def recognize_images(self, image_paths, *, prompt, config):
        return self.response


class _FailingProvider:
    def recognize_images(self, image_paths, *, prompt, config):
        raise RuntimeError("test-only provider failure")


def test_plain_injected_provider_refusal_omits_unknown_detail_keys(tmp_path):
    source = write_test_image(tmp_path / "board.png")
    provider = _ResponseProvider("抱歉，我帮不了你识别这张图。")

    with pytest.raises(ProviderError) as failure:
        recognize(source, config=Config(provider=provider))

    assert failure.value.code == "PROVIDER_REFUSED_RECOGNITION"
    assert "model" not in failure.value.details
    assert "provider" not in failure.value.details


def test_plain_injected_provider_failure_omits_unknown_model_detail(tmp_path):
    source = write_test_image(tmp_path / "board.png")

    with pytest.raises(ProviderError) as failure:
        recognize(source, config=Config(provider=_FailingProvider()))

    assert "model" not in failure.value.details


def test_provider_error_details_keep_known_model_and_provider():
    provider = _ResponseProvider("Sorry, this request cannot be completed.")
    resolved_provider = ResolvedVisionProvider(
        value=provider,
        name="known-provider",
        model="known-model",
        built_in=True,
    )

    with pytest.raises(ProviderError) as failure:
        call_vision_provider(
            resolved_provider,
            (Path("board.png"),),
            prompt="Recognize this image.",
            config=Config(provider=provider),
        )

    assert failure.value.details["model"] == "known-model"
    assert failure.value.details["provider"] == "known-provider"
