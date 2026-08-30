"""Focused public contract for scalar merged-image recognition and resume."""

from __future__ import annotations

import importlib

import pytest

from ocrllm import recognize_images_to_markdown, resume_images_to_markdown
from ocrllm.errors import AllCandidatesExhausted, OutputError, ProviderError
from ocrllm.providers.google_genai.provider_settings import GoogleGenAISettings
from ocrllm.providers.provider_model import ProviderModel
from ocrllm.providers.vision_provider_response import VisionProviderResponse
from write_test_image import write_test_image


executor = importlib.import_module("ocrllm.execute_merged_image_plan")


def _provider(model: str) -> ProviderModel:
    return ProviderModel(
        vendor="google",
        model=model,
        adapter_id="google_genai",
        settings=GoogleGenAISettings(api_key="test-only-google-key"),
        supports_plain_ocr=True,
        supports_detail_ocr=True,
        supports_audio=False,
        default_image_batch_size=2,
        default_audio_minutes=None,
        retry_rules={},
    )


def _three_batches(tmp_path):
    images = tuple(
        write_test_image(tmp_path / "frames" / f"frame-{index}.png")
        for index in range(4)
    )
    return ((images[0], images[1]), (images[2],), (images[3],))


def test_complete_merged_image_run_publishes_one_ordered_file(tmp_path, monkeypatch):
    batches = _three_batches(tmp_path)[:2]
    output = tmp_path / "frames_ocrllm.md"
    calls: list[tuple[str, ...]] = []

    def succeed(_provider, paths, **_kwargs):
        calls.append(tuple(path.name for path in paths))
        call_index = len(calls)
        return VisionProviderResponse(
            markdown=f"recognized slot {call_index}",
            input_tokens=call_index * 10,
            output_tokens=call_index,
        )

    monkeypatch.setattr(executor, "recognize_provider_model_images", succeed)

    result = recognize_images_to_markdown(
        batches,
        provider=_provider("gemini-test-a"),
        image_task="plain_ocr",
    )

    assert result.status == "complete"
    assert calls == [("frame-0.png", "frame-1.png"), ("frame-2.png",)]
    assert result.markdown.index("recognized slot 1") < result.markdown.index(
        "recognized slot 2"
    )
    assert output.read_text(encoding="utf-8") == result.markdown
    assert not (tmp_path / "frames_ocrllm.ocrllm-state.json").exists()
    assert result.metadata["current_provider_model_usage"] == (
        {
            "vendor": "google",
            "model": "gemini-test-a",
            "calls": 2,
            "input_tokens": 30,
            "output_tokens": 3,
        },
    )


def test_partial_run_continues_later_slots_and_retains_resume_state(
    tmp_path,
    monkeypatch,
):
    batches = _three_batches(tmp_path)
    output = tmp_path / "result.md"
    call_index = 0

    def fail_middle(_provider, _paths, **_kwargs):
        nonlocal call_index
        call_index += 1
        if call_index == 2:
            raise ProviderError(
                "The provider rejected this slot.",
                code="PROVIDER_REQUEST_INVALID",
                details={"provider_calls_attempted": 1},
            )
        return VisionProviderResponse(markdown=f"slot {call_index}")

    monkeypatch.setattr(executor, "recognize_provider_model_images", fail_middle)

    result = recognize_images_to_markdown(
        batches,
        provider=_provider("gemini-test-a"),
        image_task="detail_ocr",
        output_path=output,
    )

    assert call_index == 3
    assert result.status == "partial"
    assert "slot 1" in result.markdown
    assert "OCRLLM_FAILED_IMAGE_SLOT index=2 sources=3" in result.markdown
    assert "slot 3" in result.markdown
    assert (tmp_path / "result.ocrllm-state.json").is_file()
    assert result.metadata["failed_slots"] == (
        {
            "slot_index": 1,
            "provider": "google",
            "model": "gemini-test-a",
            "code": "PROVIDER_REQUEST_INVALID",
            "description": "The provider rejected this slot.",
        },
    )


def test_resume_uses_changed_provider_only_for_failed_slot(tmp_path, monkeypatch):
    batches = _three_batches(tmp_path)
    output = tmp_path / "result.md"
    first_call = 0

    def first_run(_provider, _paths, **_kwargs):
        nonlocal first_call
        first_call += 1
        if first_call == 2:
            raise ProviderError(
                "Temporary model failure.",
                code="PROVIDER_UNAVAILABLE",
                details={"provider_calls_attempted": 1},
            )
        return VisionProviderResponse(markdown=f"first {first_call}")

    monkeypatch.setattr(executor, "recognize_provider_model_images", first_run)
    partial = recognize_images_to_markdown(
        batches,
        provider=_provider("gemini-test-a"),
        image_task="plain_ocr",
        output_path=output,
    )
    assert partial.status == "partial"

    resumed_calls = 0

    def second_run(_provider, paths, **_kwargs):
        nonlocal resumed_calls
        resumed_calls += 1
        assert tuple(path.name for path in paths) == ("frame-2.png",)
        return VisionProviderResponse(
            markdown="recovered second slot",
            input_tokens=8,
            output_tokens=2,
        )

    monkeypatch.setattr(executor, "recognize_provider_model_images", second_run)
    resumed = resume_images_to_markdown(
        batches,
        provider=_provider("gemini-test-b"),
        output_path=output,
    )

    assert resumed_calls == 1
    assert resumed.status == "complete"
    assert resumed.metadata["reused_slot_count"] == 2
    assert resumed.metadata["provider_call_count"] == 1
    assert resumed.markdown.index("first 1") < resumed.markdown.index(
        "recovered second slot"
    ) < resumed.markdown.index("first 3")
    assert not (tmp_path / "result.ocrllm-state.json").exists()


def test_zero_settled_slots_raise_and_keep_state_without_markdown(
    tmp_path,
    monkeypatch,
):
    batches = _three_batches(tmp_path)[:2]
    output = tmp_path / "result.md"
    calls = 0

    def fail(_provider, _paths, **_kwargs):
        nonlocal calls
        calls += 1
        raise ProviderError(
            "No response from this model.",
            code="PROVIDER_UNAVAILABLE",
            details={"provider_calls_attempted": 1},
        )

    monkeypatch.setattr(executor, "recognize_provider_model_images", fail)

    with pytest.raises(AllCandidatesExhausted) as captured:
        recognize_images_to_markdown(
            batches,
            provider=_provider("gemini-test-a"),
            image_task="plain_ocr",
            output_path=output,
        )

    assert calls == 2
    assert captured.value.details["provider_calls_attempted"] == 2
    assert (tmp_path / "result.ocrllm-state.json").is_file()
    assert not output.exists()


def test_mixed_parent_default_rejects_before_provider_dispatch(tmp_path, monkeypatch):
    images = (
        write_test_image(tmp_path / "first" / "a.png"),
        write_test_image(tmp_path / "second" / "b.png"),
    )
    called = False

    def should_not_run(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError

    monkeypatch.setattr(executor, "recognize_provider_model_images", should_not_run)

    with pytest.raises(OutputError) as captured:
        recognize_images_to_markdown(
            ((images[0],), (images[1],)),
            provider=_provider("gemini-test-a"),
            image_task="plain_ocr",
        )

    assert getattr(captured.value, "code", None) == "OUTPUT_PATH_INVALID"
    assert called is False
