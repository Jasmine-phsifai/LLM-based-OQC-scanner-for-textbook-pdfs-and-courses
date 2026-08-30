"""Focused public contract for merged-image provider topologies and resume."""

from __future__ import annotations

import hashlib
import importlib
from threading import Event, Lock
from types import SimpleNamespace

import pytest

from ocrllm import (
    recognize_images_to_markdown,
    repair_images_to_markdown,
    resume_images_to_markdown,
    resume_video,
)
from ocrllm.errors import (
    AllCandidatesExhausted,
    ConfigError,
    InvalidSource,
    OutputError,
    ProviderError,
    ResumeStateError,
)
from ocrllm.providers.google_genai.provider_settings import GoogleGenAISettings
from ocrllm.providers.provider_model import ProviderModel
from ocrllm.providers.vision_provider_response import VisionProviderResponse
from write_test_image import write_test_image


executor = importlib.import_module("ocrllm.execute_merged_image_plan")


class _NestedGooglePart:
    @staticmethod
    def from_bytes(*, data: bytes, mime_type: str):
        return SimpleNamespace(data=data, mime_type=mime_type)


class _NestedGoogleHttpOptions:
    def __init__(self, *, timeout: int) -> None:
        self.timeout = timeout


class _NestedGoogleModels:
    def __init__(self, models, slot_digests, behavior) -> None:
        self.served_models = tuple(models)
        self.slot_digests = slot_digests
        self.behavior = behavior
        self.calls: list[tuple[str, int]] = []
        self.lock = Lock()

    def list(self):
        return tuple(
            SimpleNamespace(
                name=f"models/{model}",
                supported_actions=["generateContent"],
            )
            for model in self.served_models
        )

    def generate_content(self, *, model: str, contents):
        part = next(value for value in contents if type(value) is not str)
        slot_index = self.slot_digests[hashlib.sha256(part.data).hexdigest()]
        with self.lock:
            self.calls.append((model, slot_index))
        return self.behavior(model, slot_index)


class _NestedGoogleClient:
    def __init__(self, models: _NestedGoogleModels) -> None:
        self.models = models
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _NestedGoogleModule:
    types = SimpleNamespace(
        HttpOptions=_NestedGoogleHttpOptions,
        Part=_NestedGooglePart,
    )

    def __init__(self, models, slot_digests, behavior) -> None:
        self.models = _NestedGoogleModels(models, slot_digests, behavior)
        self.clients: list[_NestedGoogleClient] = []

    def Client(self, **_kwargs):
        client = _NestedGoogleClient(self.models)
        self.clients.append(client)
        return client


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


def _four_single_batches(tmp_path):
    images = tuple(
        write_test_image(
            tmp_path / "nested" / f"slot-{index}.png",
            color=(index * 30, index * 20, index * 10),
        )
        for index in range(4)
    )
    return tuple((image,) for image in images)


def _slot_digests(batches):
    return {
        hashlib.sha256(batch[0].read_bytes()).hexdigest(): index
        for index, batch in enumerate(batches)
    }


def _install_nested_google(monkeypatch, batches, models, behavior):
    fake = _NestedGoogleModule(models, _slot_digests(batches), behavior)
    adapter = importlib.import_module("ocrllm.providers.google_genai.recognize_images")
    monkeypatch.setattr(adapter, "load_google_genai", lambda: fake)
    return fake


def _google_image_response(markdown: str, *, input_tokens: int, output_tokens: int):
    return SimpleNamespace(
        text=markdown,
        candidates=(),
        usage_metadata=SimpleNamespace(
            prompt_token_count=input_tokens,
            candidates_token_count=output_tokens,
        ),
    )


def test_invalid_merged_image_batch_shapes_report_zero_provider_calls(
    tmp_path,
    monkeypatch,
):
    output = tmp_path / "result.md"
    called = False

    def should_not_run(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError

    monkeypatch.setattr(executor, "recognize_provider_model_images", should_not_run)
    for invalid in ((), ((),), ((object(),),)):
        with pytest.raises(InvalidSource) as captured:
            recognize_images_to_markdown(
                invalid,  # type: ignore[arg-type]
                provider=_provider("gemini-test-a"),
                image_task="detail_ocr",
                output_path=output,
            )
        assert captured.value.code == "SOURCE_INVALID"
        assert captured.value.details["provider_calls_attempted"] == 0

    assert called is False
    assert not output.exists()
    assert not (tmp_path / "result.ocrllm-state.json").exists()


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


def test_flat_fallback_resume_restarts_at_first_candidate_for_failed_slot(
    tmp_path,
    monkeypatch,
):
    batches = _three_batches(tmp_path)[:2]
    output = tmp_path / "result.md"
    first_run_calls = 0

    def first_run(_provider, _paths, **_kwargs):
        nonlocal first_run_calls
        first_run_calls += 1
        if first_run_calls == 2:
            raise ProviderError(
                "Temporary model failure.",
                code="PROVIDER_UNAVAILABLE",
                details={"provider_calls_attempted": 1},
            )
        return VisionProviderResponse(markdown="settled before resume")

    monkeypatch.setattr(executor, "recognize_provider_model_images", first_run)
    partial = recognize_images_to_markdown(
        batches,
        provider=_provider("gemini-initial"),
        image_task="plain_ocr",
        output_path=output,
    )
    assert partial.status == "partial"

    calls: list[str] = []

    def resume_run(provider, paths, **_kwargs):
        calls.append(provider.model)
        assert tuple(path.name for path in paths) == ("frame-2.png",)
        if provider.model == "gemini-test-a":
            raise ProviderError(
                "First resume candidate still unavailable.",
                code="PROVIDER_UNAVAILABLE",
                details={"provider_calls_attempted": 1},
            )
        return VisionProviderResponse(markdown="settled by fallback")

    monkeypatch.setattr(executor, "recognize_provider_model_images", resume_run)
    resumed = resume_images_to_markdown(
        batches,
        provider=[_provider("gemini-test-a"), _provider("gemini-test-b")],
        output_path=output,
    )

    assert calls == ["gemini-test-a", "gemini-test-b"]
    assert resumed.status == "complete"
    assert resumed.metadata["reused_slot_count"] == 1
    assert resumed.metadata["provider_call_count"] == 2
    assert resumed.metadata["provider_failures"][0]["model"] == "gemini-test-a"
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


def test_flat_fallback_stops_on_success_and_rotates_next_slot(
    tmp_path,
    monkeypatch,
):
    batches = _three_batches(tmp_path)[:2]
    output = tmp_path / "result.md"
    first = _provider("gemini-test-a")
    second = _provider("gemini-test-b")
    calls: list[tuple[str, str]] = []

    def fallback(provider, paths, **_kwargs):
        source = paths[0].name
        calls.append((provider.model, source))
        if (provider.model, source) == ("gemini-test-a", "frame-0.png"):
            raise ProviderError(
                "A" * 600,
                code="PROVIDER_TIMEOUT",
                details={"provider_calls_attempted": 1},
            )
        if (provider.model, source) == ("gemini-test-b", "frame-2.png"):
            raise ProviderError(
                "The second provider was unavailable.",
                code="PROVIDER_UNAVAILABLE",
                details={"provider_calls_attempted": 1},
            )
        return VisionProviderResponse(
            markdown=f"recognized {provider.model} {source}",
            input_tokens=10,
            output_tokens=2,
        )

    monkeypatch.setattr(executor, "recognize_provider_model_images", fallback)
    result = recognize_images_to_markdown(
        batches,
        provider=[first, second],
        image_task="detail_ocr",
        output_path=output,
    )

    assert calls == [
        ("gemini-test-a", "frame-0.png"),
        ("gemini-test-b", "frame-0.png"),
        ("gemini-test-b", "frame-2.png"),
        ("gemini-test-a", "frame-2.png"),
    ]
    assert result.status == "complete"
    assert result.warnings == (
        "Recognition completed after one or more provider candidates failed.",
    )
    failures = result.metadata["provider_failures"]
    assert tuple(
        (row["slot_index"], row["model"], row["code"]) for row in failures
    ) == (
        (0, "gemini-test-a", "PROVIDER_TIMEOUT"),
        (1, "gemini-test-b", "PROVIDER_UNAVAILABLE"),
    )
    assert len(failures[0]["description"]) == 512
    assert failures[0]["description"].endswith("...")
    assert result.metadata["provider_call_count"] == 4
    assert not (tmp_path / "result.ocrllm-state.json").exists()


def test_flat_fallback_exhaustion_keeps_only_terminal_slot_failure(
    tmp_path,
    monkeypatch,
):
    batches = _three_batches(tmp_path)[:1]
    output = tmp_path / "result.md"
    calls: list[str] = []

    def fail(provider, _paths, **_kwargs):
        calls.append(provider.model)
        raise ProviderError(
            f"{provider.model} failed.",
            code="PROVIDER_UNAVAILABLE",
            details={"provider_calls_attempted": 1},
        )

    monkeypatch.setattr(executor, "recognize_provider_model_images", fail)
    with pytest.raises(AllCandidatesExhausted) as captured:
        recognize_images_to_markdown(
            batches,
            provider=[_provider("gemini-test-a"), _provider("gemini-test-b")],
            image_task="plain_ocr",
            output_path=output,
        )

    assert calls == ["gemini-test-a", "gemini-test-b"]
    assert captured.value.details["provider_calls_attempted"] == 2
    assert captured.value.details["failed_slots"] == (
        {
            "slot_index": 0,
            "provider": "google",
            "model": "gemini-test-b",
            "code": "PROVIDER_UNAVAILABLE",
            "description": "gemini-test-b failed.",
        },
    )
    assert "provider_failures" not in captured.value.details
    assert not output.exists()
    assert (tmp_path / "result.ocrllm-state.json").is_file()


def test_flat_provider_shape_rejects_before_output_or_dispatch(
    tmp_path,
    monkeypatch,
):
    batches = _three_batches(tmp_path)[:1]
    output = tmp_path / "result.md"
    provider = _provider("gemini-test-a")
    called = False

    class ProviderList(list):
        pass

    def should_not_run(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError

    monkeypatch.setattr(executor, "recognize_provider_model_images", should_not_run)
    invalid_values = (
        (),
        [],
        ProviderList([provider]),
        [provider, object()],
        [[]],
        [provider, [provider]],
        [[provider], provider],
        [[[provider]]],
        [ProviderList([provider])],
        [[provider, provider]],
        [[_provider(f"gemini-lane-{index}")] for index in range(33)],
        [provider, provider],
    )
    for invalid in invalid_values:
        with pytest.raises(ConfigError) as captured:
            recognize_images_to_markdown(
                batches,
                provider=invalid,  # type: ignore[arg-type]
                image_task="plain_ocr",
                output_path=output,
            )
        assert captured.value.details["provider_calls_attempted"] == 0
        assert not output.exists()
        assert not (tmp_path / "result.ocrllm-state.json").exists()
    assert called is False


def test_nested_image_lanes_advance_independently_and_publish_by_slot(
    tmp_path,
    monkeypatch,
):
    batches = _four_single_batches(tmp_path)
    output = tmp_path / "nested.md"
    lane_zero_first = "gemini-lane-zero-a"
    lane_zero_second = "gemini-lane-zero-b"
    lane_one = "gemini-lane-one"
    lane_one_slot_three_started = Event()
    events: list[tuple[str, str, int]] = []
    events_lock = Lock()

    def record(kind: str, model: str, slot_index: int) -> None:
        with events_lock:
            events.append((kind, model, slot_index))

    def behavior(model: str, slot_index: int):
        record("start", model, slot_index)
        if model == lane_zero_first and slot_index == 0:
            assert lane_one_slot_three_started.wait(timeout=5.0)
            record("end", model, slot_index)
            raise ProviderError(
                "The first lane candidate timed out.",
                code="PROVIDER_TIMEOUT",
                details={"provider_calls_attempted": 1},
            )
        if slot_index == 2:
            record("end", model, slot_index)
            raise ProviderError(
                f"{model} could not settle slot two.",
                code="PROVIDER_UNAVAILABLE",
                details={"provider_calls_attempted": 1},
            )
        if model == lane_one and slot_index == 3:
            lane_one_slot_three_started.set()
        record("end", model, slot_index)
        return _google_image_response(
            f"slot {slot_index} {model}",
            input_tokens=100 + slot_index,
            output_tokens=10 + slot_index,
        )

    fake = _install_nested_google(
        monkeypatch,
        batches,
        (lane_zero_first, lane_zero_second, lane_one),
        behavior,
    )
    result = recognize_images_to_markdown(
        batches,
        provider=[
            [_provider(lane_zero_first), _provider(lane_zero_second)],
            [_provider(lane_one)],
        ],
        image_task="detail_ocr",
        output_path=output,
    )

    starts = [event for event in events if event[0] == "start"]
    assert [event[1:] for event in starts if event[1] != lane_one] == [
        (lane_zero_first, 0),
        (lane_zero_second, 0),
        (lane_zero_second, 2),
        (lane_zero_first, 2),
    ]
    assert [event[1:] for event in starts if event[1] == lane_one] == [
        (lane_one, 1),
        (lane_one, 3),
    ]
    assert events.index(("start", lane_one, 3)) < events.index(
        ("end", lane_zero_first, 0)
    )
    assert ("start", lane_one, 2) not in events
    assert result.status == "partial"
    assert result.metadata["provider_call_count"] == 6
    assert tuple(
        (row["model"], row["calls"], row["input_tokens"], row["output_tokens"])
        for row in result.metadata["current_provider_model_usage"]
    ) == (
        (lane_zero_first, 2, None, None),
        (lane_zero_second, 2, None, None),
        (lane_one, 2, 204, 24),
    )
    assert tuple(
        (row["slot_index"], row["model"], row["code"])
        for row in result.metadata["provider_failures"]
    ) == ((0, lane_zero_first, "PROVIDER_TIMEOUT"),)
    assert result.metadata["failed_slots"][0]["slot_index"] == 2
    assert result.metadata["failed_slots"][0]["model"] == lane_zero_first
    assert result.markdown.index(f"slot 0 {lane_zero_second}") < result.markdown.index(
        f"slot 1 {lane_one}"
    ) < result.markdown.index("OCRLLM_FAILED_IMAGE_SLOT index=3") < result.markdown.index(
        f"slot 3 {lane_one}"
    )
    assert output.read_text(encoding="utf-8") == result.markdown
    assert (tmp_path / "nested.ocrllm-state.json").is_file()
    assert all(client.closed for client in fake.clients)


def test_nested_image_resume_uses_absolute_slot_with_changed_lane_count(
    tmp_path,
    monkeypatch,
):
    batches = _four_single_batches(tmp_path)
    output = tmp_path / "resume.md"
    first_lane = "gemini-first-lane"
    second_lane = "gemini-second-lane"

    def first_behavior(model: str, slot_index: int):
        if model == first_lane and slot_index == 2:
            raise ProviderError(
                "The original lane could not settle slot two.",
                code="PROVIDER_UNAVAILABLE",
                details={"provider_calls_attempted": 1},
            )
        return _google_image_response(
            f"initial slot {slot_index}",
            input_tokens=20 + slot_index,
            output_tokens=2,
        )

    first_fake = _install_nested_google(
        monkeypatch,
        batches,
        (first_lane, second_lane),
        first_behavior,
    )
    partial = recognize_images_to_markdown(
        batches,
        provider=[[_provider(first_lane)], [_provider(second_lane)]],
        image_task="plain_ocr",
        output_path=output,
    )
    assert partial.status == "partial"
    assert set(first_fake.models.calls) == {
        (first_lane, 0),
        (first_lane, 2),
        (second_lane, 1),
        (second_lane, 3),
    }

    resume_models = (
        "gemini-resume-lane-zero",
        "gemini-resume-lane-one",
        "gemini-resume-lane-two",
    )

    def resume_behavior(model: str, slot_index: int):
        return _google_image_response(
            f"resumed slot {slot_index} {model}",
            input_tokens=50,
            output_tokens=5,
        )

    resume_fake = _install_nested_google(
        monkeypatch,
        batches,
        resume_models,
        resume_behavior,
    )
    resumed = resume_video(
        batches,
        media_type="image",
        providers=[[_provider(model)] for model in resume_models],
        output_path=output,
    )

    assert resume_fake.models.calls == [(resume_models[2], 2)]
    assert resumed.status == "complete"
    assert resumed.metadata["reused_slot_count"] == 3
    assert resumed.metadata["provider_call_count"] == 1
    assert resumed.markdown.index("initial slot 0") < resumed.markdown.index(
        "initial slot 1"
    ) < resumed.markdown.index(
        f"resumed slot 2 {resume_models[2]}"
    ) < resumed.markdown.index("initial slot 3")
    assert not (tmp_path / "resume.ocrllm-state.json").exists()
    assert all(client.closed for client in first_fake.clients)
    assert all(client.closed for client in resume_fake.clients)


def _make_repairable_partial(
    tmp_path,
    monkeypatch,
    batches,
    *,
    failed_slots: frozenset[int],
):
    initial_model = "gemini-repair-initial"

    def initial_behavior(model: str, slot_index: int):
        if slot_index in failed_slots:
            raise ProviderError(
                f"Initial slot {slot_index} failed.",
                code="PROVIDER_UNAVAILABLE",
                details={"provider_calls_attempted": 1},
            )
        return _google_image_response(
            f"initial settled slot {slot_index}",
            input_tokens=10 + slot_index,
            output_tokens=2,
        )

    fake = _install_nested_google(
        monkeypatch,
        batches,
        (initial_model,),
        initial_behavior,
    )
    result = recognize_images_to_markdown(
        batches,
        provider=_provider(initial_model),
        image_task="detail_ocr",
    )
    assert result.status == "partial"
    assert result.output_path is not None
    output = result.output_path
    state_path = output.with_name(f"{output.stem}.ocrllm-state.json")
    assert state_path.is_file()
    state_path.unlink()
    return output, fake


def test_image_repair_preserves_paid_success_and_flat_lane_rotation(
    tmp_path,
    monkeypatch,
):
    batches = _four_single_batches(tmp_path)
    source_hashes = tuple(
        hashlib.sha256(batch[0].read_bytes()).hexdigest() for batch in batches
    )
    output, initial_fake = _make_repairable_partial(
        tmp_path,
        monkeypatch,
        batches,
        failed_slots=frozenset({1, 2}),
    )
    first_model = "gemini-repair-a"
    second_model = "gemini-repair-b"

    def repair_behavior(model: str, slot_index: int):
        if (slot_index, model) in {
            (1, first_model),
            (2, first_model),
            (2, second_model),
        }:
            raise ProviderError(
                f"{model} could not repair slot {slot_index}.",
                code="PROVIDER_TIMEOUT",
                details={"provider_calls_attempted": 1},
            )
        return _google_image_response(
            f"repaired slot {slot_index} with {model}",
            input_tokens=100 + slot_index,
            output_tokens=10 + slot_index,
        )

    repair_fake = _install_nested_google(
        monkeypatch,
        batches,
        (first_model, second_model),
        repair_behavior,
    )
    partial = repair_images_to_markdown(
        batches,
        provider=[_provider(first_model), _provider(second_model)],
        image_task="detail_ocr",
        output_path=output,
    )

    assert repair_fake.models.calls == [
        (first_model, 1),
        (second_model, 1),
        (second_model, 2),
        (first_model, 2),
    ]
    assert partial.status == "partial"
    assert partial.metadata["provider_call_count"] == 4
    assert partial.metadata["repaired_slot_count"] == 1
    assert partial.metadata["failed_slots"][0]["slot_index"] == 2
    assert tuple(
        (row["slot_index"], row["model"])
        for row in partial.metadata["provider_failures"]
    ) == ((1, first_model),)
    assert "initial settled slot 0" in partial.markdown
    assert f"repaired slot 1 with {second_model}" in partial.markdown
    assert "OCRLLM_FAILED_IMAGE_SLOT index=3 sources=3" in partial.markdown
    assert "initial settled slot 3" in partial.markdown
    assert output.read_text(encoding="utf-8") == partial.markdown
    assert not output.with_name(f"{output.stem}.ocrllm-state.json").exists()

    final_model = "gemini-repair-final"
    final_fake = _install_nested_google(
        monkeypatch,
        batches,
        (final_model,),
        lambda model, slot_index: _google_image_response(
            f"finally repaired slot {slot_index} with {model}",
            input_tokens=77,
            output_tokens=7,
        ),
    )
    completed = repair_images_to_markdown(
        batches,
        provider=_provider(final_model),
        image_task="detail_ocr",
        output_path=output,
    )

    assert final_fake.models.calls == [(final_model, 2)]
    assert completed.status == "complete"
    assert completed.metadata["repair_marker_count"] == 1
    assert completed.metadata["provider_call_count"] == 1
    assert "OCRLLM_FAILED_IMAGE_SLOT" not in completed.markdown
    assert f"repaired slot 1 with {second_model}" in completed.markdown
    assert f"finally repaired slot 2 with {final_model}" in completed.markdown
    assert tuple(
        hashlib.sha256(batch[0].read_bytes()).hexdigest() for batch in batches
    ) == source_hashes
    assert all(client.closed for client in initial_fake.clients)
    assert all(client.closed for client in repair_fake.clients)
    assert all(client.closed for client in final_fake.clients)


def test_image_repair_uses_absolute_nested_lane_assignment(tmp_path, monkeypatch):
    batches = _four_single_batches(tmp_path)
    output, _ = _make_repairable_partial(
        tmp_path,
        monkeypatch,
        batches,
        failed_slots=frozenset({1, 2}),
    )
    lane_zero = "gemini-repair-lane-zero"
    lane_one = "gemini-repair-lane-one"
    fake = _install_nested_google(
        monkeypatch,
        batches,
        (lane_zero, lane_one),
        lambda model, slot_index: _google_image_response(
            f"nested repair {slot_index} {model}",
            input_tokens=20 + slot_index,
            output_tokens=2,
        ),
    )

    result = repair_images_to_markdown(
        batches,
        provider=[[_provider(lane_zero)], [_provider(lane_one)]],
        image_task="detail_ocr",
    )

    assert fake.models.calls == [(lane_one, 1), (lane_zero, 2)]
    assert result.status == "complete"
    assert tuple(row["model"] for row in result.metadata["current_provider_model_usage"]) == (
        lane_zero,
        lane_one,
    )


def test_image_repair_preflight_rejects_state_and_bad_markers_before_provider(
    tmp_path,
    monkeypatch,
):
    batches = _four_single_batches(tmp_path)
    output, _ = _make_repairable_partial(
        tmp_path,
        monkeypatch,
        batches,
        failed_slots=frozenset({1}),
    )
    model = "gemini-repair-preflight"
    fake = _install_nested_google(
        monkeypatch,
        batches,
        (model,),
        lambda _model, _slot: (_ for _ in ()).throw(AssertionError()),
    )
    valid_markdown = output.read_text(encoding="utf-8")
    state_path = output.with_name(f"{output.stem}.ocrllm-state.json")
    state_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ResumeStateError) as state_error:
        repair_images_to_markdown(
            batches,
            provider=_provider(model),
            image_task="detail_ocr",
            output_path=output,
        )
    assert state_error.value.details["provider_calls_attempted"] == 0
    state_path.unlink()

    invalid_markdowns = (
        valid_markdown.replace("sources=2", "sources=99"),
        valid_markdown + "\n<!-- OCRLLM_FAILED_IMAGE_SLOT index=2 sources=2 code=PROVIDER_UNAVAILABLE -->\n",
        valid_markdown.replace("OCRLLM_FAILED_IMAGE_SLOT", "OCRLLM_FAILED_SLOT"),
    )
    for invalid_markdown in invalid_markdowns:
        output.write_text(invalid_markdown, encoding="utf-8")
        with pytest.raises(InvalidSource) as marker_error:
            repair_images_to_markdown(
                batches,
                provider=_provider(model),
                image_task="detail_ocr",
                output_path=output,
            )
        assert marker_error.value.details["provider_calls_attempted"] == 0

    assert fake.models.calls == []
