"""Public scalar-or-flat merged-audio recognition and resume behavior."""

from __future__ import annotations

import importlib
import re
import subprocess
from pathlib import Path
from threading import Event, Lock
from types import SimpleNamespace

import pytest

from ocrllm import (
    AudioSlice,
    ProviderModel,
    recognize_audio_to_markdown,
    resume_audio_to_markdown,
    split_audio,
)
from ocrllm.errors import AllCandidatesExhausted, ConfigError, InvalidSource, ProviderError
from ocrllm.providers.google_genai.provider_settings import GoogleGenAISettings


MODEL = "gemini-2.5-flash"
SHORT_FIXTURE = (
    Path(__file__).parent / "fixtures" / "audio" / "a1" / "mp3" / "valid_cbr.mp3"
)


class _HttpOptions:
    def __init__(self, *, timeout: int) -> None:
        self.timeout = timeout


class _Part:
    @staticmethod
    def from_bytes(*, data: bytes, mime_type: str):
        return SimpleNamespace(data=data, mime_type=mime_type)


class _Files:
    def __init__(self) -> None:
        self.upload_count = 0
        self.delete_count = 0
        self.lock = Lock()
        self.active_names: set[str] = set()
        self.maximum_active = 0
        self.upload_paths: list[Path] = []

    def upload(self, *, file):
        assert Path(file).is_file()
        with self.lock:
            self.upload_count += 1
            name = f"files/test-{self.upload_count}"
            self.active_names.add(name)
            self.maximum_active = max(self.maximum_active, len(self.active_names))
            self.upload_paths.append(Path(file))
        return SimpleNamespace(
            name=name,
            state=SimpleNamespace(name="ACTIVE"),
        )

    def delete(self, *, name: str):
        assert name.startswith("files/test-")
        with self.lock:
            self.delete_count += 1
            self.active_names.remove(name)


class _Models:
    def __init__(
        self,
        responses: list[str | Exception],
        served_models: tuple[str, ...],
        behavior=None,
    ) -> None:
        self.responses = responses
        self.served_models = served_models
        self.behavior = behavior
        self.generate_count = 0
        self.calls: list[str] = []
        self.slot_calls: list[tuple[str, int]] = []
        self.lock = Lock()

    def list(self):
        return tuple(
            SimpleNamespace(
                name=f"models/{model}",
                supported_actions=["generateContent"],
                input_token_limit=1_048_576,
            )
            for model in self.served_models
        )

    def generate_content(self, *, model: str, contents):
        assert model in self.served_models
        assert type(contents[0]) is str
        slot_index = _slot_index_from_prompt(contents[0])
        with self.lock:
            self.generate_count += 1
            call_index = self.generate_count
            self.calls.append(model)
            self.slot_calls.append((model, slot_index))
            response = (
                None if self.behavior is not None else self.responses.pop(0)
            )
        if self.behavior is not None:
            response = self.behavior(model, slot_index)
        if isinstance(response, Exception):
            raise response
        if type(response) is SimpleNamespace:
            return response
        return SimpleNamespace(
            text=response,
            candidates=(),
            prompt_feedback=None,
            usage_metadata=SimpleNamespace(
                prompt_token_count=100 + call_index,
                candidates_token_count=10 + call_index,
            ),
        )


class _Client:
    def __init__(self, files: _Files, models: _Models) -> None:
        self.files = files
        self.models = models
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeGoogleModule:
    types = SimpleNamespace(HttpOptions=_HttpOptions, Part=_Part)

    def __init__(
        self,
        responses: list[str | Exception],
        served_models: tuple[str, ...],
        behavior=None,
    ) -> None:
        self.files = _Files()
        self.models = _Models(responses, served_models, behavior)
        self.clients: list[_Client] = []

    def Client(self, **_kwargs):
        client = _Client(self.files, self.models)
        self.clients.append(client)
        return client


def _provider(model: str = MODEL) -> ProviderModel:
    return ProviderModel(
        vendor="google",
        model=model,
        adapter_id="google_genai",
        settings=GoogleGenAISettings(api_key="test-only-google-key"),
        supports_plain_ocr=True,
        supports_detail_ocr=True,
        supports_audio=True,
        default_image_batch_size=8,
        default_audio_minutes=30,
        retry_rules={},
    )


def _install_fake_sdk(
    monkeypatch,
    responses: list[str | Exception],
    *,
    served_models: tuple[str, ...] = (MODEL,),
    behavior=None,
):
    fake = _FakeGoogleModule(responses, served_models, behavior)
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_uploaded_mp3"
    )
    short_adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_short_mp3"
    )
    monkeypatch.setattr(adapter, "load_google_genai", lambda: fake)
    monkeypatch.setattr(short_adapter, "load_google_genai", lambda: fake)
    return fake


def _slot_index_from_prompt(prompt: str) -> int:
    matched = re.search(
        r"Transcribe only content occurring from ([0-9]+(?:\.[0-9]+)?) to ",
        prompt,
    )
    if matched is None:
        return 0
    return int(float(matched.group(1)) // 60.0)


def _raw_audio_response(text: str, *, input_tokens: int, output_tokens: int):
    return SimpleNamespace(
        text=text,
        candidates=(),
        prompt_feedback=None,
        usage_metadata=SimpleNamespace(
            prompt_token_count=input_tokens,
            candidates_token_count=output_tokens,
        ),
    )


def _write_sixty_one_second_mp3(path: Path) -> Path:
    return _write_synthetic_mp3(path, duration_seconds=61)


def _write_synthetic_mp3(path: Path, *, duration_seconds: int) -> Path:
    from ocrllm.audio.load_audio_ffmpeg_executable import (
        load_audio_ffmpeg_executable,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            str(load_audio_ffmpeg_executable()),
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:sample_rate=16000:duration={duration_seconds}",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "32k",
            str(path),
        ],
        check=False,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    return path


def test_whole_audio_publishes_default_markdown_and_no_speech_marker(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "short.mp3"
    source.write_bytes(SHORT_FIXTURE.read_bytes())
    source_bytes = source.read_bytes()
    fake = _install_fake_sdk(monkeypatch, ["NOSPEECH4OCRLLM"])

    result = recognize_audio_to_markdown(
        split_audio(source, interval_minutes=-1),
        provider=_provider(),
    )

    output = tmp_path / "short_ocrllm.md"
    assert result.status == "complete"
    assert result.source_type == "audio"
    assert result.output_path == output
    assert output.read_text(encoding="utf-8") == result.markdown
    assert "OCRLLM_NO_SPEECH_AUDIO_SLOT index=1" in result.markdown
    assert result.metadata["no_speech_slot_count"] == 1
    assert result.metadata["provider_call_count"] == 1
    assert not (tmp_path / "short_ocrllm.ocrllm-state.json").exists()
    assert source.read_bytes() == source_bytes
    assert fake.models.generate_count == 1
    assert fake.files.upload_count == fake.files.delete_count == 0
    assert all(client.closed for client in fake.clients)


def test_interval_partial_continues_and_resume_reuses_settled_slice(
    tmp_path,
    monkeypatch,
):
    source = _write_sixty_one_second_mp3(tmp_path / "lecture.mp3")
    source_bytes = source.read_bytes()
    slices = split_audio(source, interval_minutes=1)
    output = tmp_path / "result.md"
    failure = ProviderError(
        "Temporary audio provider failure.",
        code="PROVIDER_UNAVAILABLE",
    )
    fake = _install_fake_sdk(monkeypatch, ["first minute", failure])

    partial = recognize_audio_to_markdown(
        slices,
        provider=_provider(),
        output_path=output,
    )

    state_path = tmp_path / "result.ocrllm-state.json"
    assert len(slices) == 2
    assert partial.status == "partial"
    assert "first minute" in partial.markdown
    assert "OCRLLM_FAILED_AUDIO_SLOT index=2" in partial.markdown
    assert state_path.is_file()
    assert fake.models.generate_count == 2

    fake.models.responses.append("recovered final second")
    resumed = resume_audio_to_markdown(
        slices,
        provider=_provider(),
        output_path=output,
    )

    assert resumed.status == "complete"
    assert resumed.metadata["reused_slot_count"] == 1
    assert resumed.metadata["provider_call_count"] == 1
    assert resumed.metadata["historical_provider_model_usage"] == (
        {
            "vendor": "google",
            "model": MODEL,
            "calls": 2,
            "input_tokens": None,
            "output_tokens": None,
        },
    )
    assert resumed.markdown.index("first minute") < resumed.markdown.index(
        "recovered final second"
    )
    assert not state_path.exists()
    assert fake.models.generate_count == 3
    assert fake.files.upload_count == fake.files.delete_count == 3
    assert source.read_bytes() == source_bytes


def test_invalid_slice_shape_is_rejected_before_source_or_provider(tmp_path):
    source = tmp_path / "missing.mp3"
    slice_value = AudioSlice(
        source=source,
        index=0,
        logical_start_seconds=0.0,
        logical_end_seconds=1.0,
        actual_start_seconds=0.0,
        actual_end_seconds=1.0,
    )

    with pytest.raises(InvalidSource) as captured:
        recognize_audio_to_markdown(  # type: ignore[arg-type]
            [slice_value],
            provider=_provider(),
        )

    assert captured.value.code == "SOURCE_INVALID"
    assert captured.value.details["provider_calls_attempted"] == 0
    assert tuple(tmp_path.iterdir()) == ()


def test_flat_provider_shape_rejects_before_source_or_provider(tmp_path):
    source = tmp_path / "missing.mp3"
    slices = (
        AudioSlice(
            source=source,
            index=0,
            logical_start_seconds=0.0,
            logical_end_seconds=1.0,
            actual_start_seconds=0.0,
            actual_end_seconds=1.0,
        ),
    )
    provider = _provider()

    class ProviderList(list):
        pass

    invalid_values = (
        (),
        [],
        ProviderList([provider]),
        (provider,),
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
            recognize_audio_to_markdown(
                slices,
                provider=invalid,  # type: ignore[arg-type]
                output_path=tmp_path / "result.md",
            )
        assert captured.value.code == "CONFIG_INVALID"
        assert captured.value.details["provider_calls_attempted"] == 0
        assert tuple(tmp_path.iterdir()) == ()


def test_flat_audio_fallback_stops_on_success_and_rotates_next_slice(
    tmp_path,
    monkeypatch,
):
    source = _write_sixty_one_second_mp3(tmp_path / "lecture.mp3")
    slices = split_audio(source, interval_minutes=1)
    first_model = "gemini-test-a"
    second_model = "gemini-test-b"
    fake = _install_fake_sdk(
        monkeypatch,
        [
            ProviderError(
                "A" * 600,
                code="PROVIDER_TIMEOUT",
                details={"provider_calls_attempted": 1},
            ),
            "first minute",
            ProviderError(
                "The second provider was unavailable.",
                code="PROVIDER_UNAVAILABLE",
                details={"provider_calls_attempted": 1},
            ),
            "final second",
        ],
        served_models=(first_model, second_model),
    )

    result = recognize_audio_to_markdown(
        slices,
        provider=[_provider(first_model), _provider(second_model)],
        output_path=tmp_path / "result.md",
    )

    assert fake.models.calls == [
        first_model,
        second_model,
        second_model,
        first_model,
    ]
    assert result.status == "complete"
    assert result.metadata["provider_call_count"] == 4
    assert result.warnings == (
        "Recognition completed after one or more provider candidates failed.",
    )
    failures = result.metadata["provider_failures"]
    assert tuple(
        (row["slot_index"], row["model"], row["code"]) for row in failures
    ) == (
        (0, first_model, "PROVIDER_TIMEOUT"),
        (1, second_model, "PROVIDER_UNAVAILABLE"),
    )
    assert len(failures[0]["description"]) == 512
    assert failures[0]["description"].endswith("...")
    assert fake.files.upload_count == fake.files.delete_count == 4
    assert all(client.closed for client in fake.clients)


def test_flat_audio_fallback_exhaustion_keeps_terminal_failure_only(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "short.mp3"
    source.write_bytes(SHORT_FIXTURE.read_bytes())
    slices = split_audio(source, interval_minutes=-1)
    first_model = "gemini-test-a"
    second_model = "gemini-test-b"
    fake = _install_fake_sdk(
        monkeypatch,
        [
            ProviderError(
                f"{first_model} failed.",
                code="PROVIDER_UNAVAILABLE",
                details={"provider_calls_attempted": 1},
            ),
            ProviderError(
                f"{second_model} failed.",
                code="PROVIDER_UNAVAILABLE",
                details={"provider_calls_attempted": 1},
            ),
        ],
        served_models=(first_model, second_model),
    )
    output = tmp_path / "result.md"

    with pytest.raises(AllCandidatesExhausted) as captured:
        recognize_audio_to_markdown(
            slices,
            provider=[_provider(first_model), _provider(second_model)],
            output_path=output,
        )

    assert fake.models.calls == [first_model, second_model]
    assert captured.value.details["provider_calls_attempted"] == 2
    assert captured.value.details["failed_slots"] == (
        {
            "slot_index": 0,
            "provider": "google",
            "model": second_model,
            "code": "PROVIDER_UNAVAILABLE",
            "description": f"{second_model} failed.",
        },
    )
    assert "provider_failures" not in captured.value.details
    assert not output.exists()
    assert (tmp_path / "result.ocrllm-state.json").is_file()


def test_flat_audio_resume_restarts_at_first_candidate_and_reuses_settled_slice(
    tmp_path,
    monkeypatch,
):
    source = _write_sixty_one_second_mp3(tmp_path / "lecture.mp3")
    slices = split_audio(source, interval_minutes=1)
    output = tmp_path / "result.md"
    first_model = "gemini-test-a"
    second_model = "gemini-test-b"
    def unavailable(message: str) -> ProviderError:
        return ProviderError(
            message,
            code="PROVIDER_UNAVAILABLE",
            details={"provider_calls_attempted": 1},
        )
    fake = _install_fake_sdk(
        monkeypatch,
        [
            "settled first minute",
            unavailable("First candidate failed."),
            unavailable("Second candidate failed."),
            unavailable("First resume candidate still failed."),
            "recovered final second",
        ],
        served_models=(first_model, second_model),
    )
    lane = [_provider(first_model), _provider(second_model)]

    partial = recognize_audio_to_markdown(
        slices,
        provider=lane,
        output_path=output,
    )
    assert partial.status == "partial"
    assert fake.models.calls == [first_model, first_model, second_model]

    resumed = resume_audio_to_markdown(
        slices,
        provider=lane,
        output_path=output,
    )

    assert fake.models.calls[3:] == [first_model, second_model]
    assert resumed.status == "complete"
    assert resumed.metadata["reused_slot_count"] == 1
    assert resumed.metadata["provider_call_count"] == 2
    assert resumed.markdown.index("settled first minute") < resumed.markdown.index(
        "recovered final second"
    )
    assert not (tmp_path / "result.ocrllm-state.json").exists()


def test_nested_audio_lanes_advance_independently_and_clean_every_clip(
    tmp_path,
    monkeypatch,
):
    source = _write_synthetic_mp3(
        tmp_path / "nested.mp3",
        duration_seconds=181,
    )
    slices = split_audio(source, interval_minutes=1)
    output = tmp_path / "nested.md"
    lane_zero_first = "gemini-audio-lane-zero-a"
    lane_zero_second = "gemini-audio-lane-zero-b"
    lane_one = "gemini-audio-lane-one"
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
                "The first audio lane candidate timed out.",
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
        if model == lane_one and slot_index == 1:
            return _raw_audio_response(
                "NOSPEECH4OCRLLM",
                input_tokens=201,
                output_tokens=0,
            )
        return _raw_audio_response(
            f"slot {slot_index} {model}",
            input_tokens=200 + slot_index,
            output_tokens=20 + slot_index,
        )

    fake = _install_fake_sdk(
        monkeypatch,
        [],
        served_models=(lane_zero_first, lane_zero_second, lane_one),
        behavior=behavior,
    )
    result = recognize_audio_to_markdown(
        slices,
        provider=[
            [_provider(lane_zero_first), _provider(lane_zero_second)],
            [_provider(lane_one)],
        ],
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
    assert result.metadata["no_speech_slot_count"] == 1
    assert tuple(
        (row["model"], row["calls"], row["input_tokens"], row["output_tokens"])
        for row in result.metadata["current_provider_model_usage"]
    ) == (
        (lane_zero_first, 2, None, None),
        (lane_zero_second, 2, None, None),
        (lane_one, 2, 404, 23),
    )
    assert tuple(
        (row["slot_index"], row["model"], row["code"])
        for row in result.metadata["provider_failures"]
    ) == ((0, lane_zero_first, "PROVIDER_TIMEOUT"),)
    assert result.metadata["failed_slots"][0]["slot_index"] == 2
    assert result.metadata["failed_slots"][0]["model"] == lane_zero_first
    assert result.markdown.index(f"slot 0 {lane_zero_second}") < result.markdown.index(
        "OCRLLM_NO_SPEECH_AUDIO_SLOT index=2"
    ) < result.markdown.index("OCRLLM_FAILED_AUDIO_SLOT index=3") < result.markdown.index(
        f"slot 3 {lane_one}"
    )
    assert output.read_text(encoding="utf-8") == result.markdown
    assert (tmp_path / "nested.ocrllm-state.json").is_file()
    assert fake.files.upload_count == fake.files.delete_count == 6
    assert fake.files.maximum_active == 2
    assert len(set(fake.files.upload_paths)) == 4
    assert all(not path.exists() for path in fake.files.upload_paths)
    assert all(client.closed for client in fake.clients)


def test_nested_audio_resume_uses_absolute_slot_with_changed_lane_count(
    tmp_path,
    monkeypatch,
):
    source = _write_synthetic_mp3(
        tmp_path / "resume.mp3",
        duration_seconds=181,
    )
    slices = split_audio(source, interval_minutes=1)
    output = tmp_path / "resume.md"
    first_lane = "gemini-audio-first-lane"
    second_lane = "gemini-audio-second-lane"

    def first_behavior(model: str, slot_index: int):
        if model == first_lane and slot_index == 2:
            raise ProviderError(
                "The original audio lane could not settle slot two.",
                code="PROVIDER_UNAVAILABLE",
                details={"provider_calls_attempted": 1},
            )
        return _raw_audio_response(
            f"initial slot {slot_index}",
            input_tokens=30 + slot_index,
            output_tokens=3,
        )

    first_fake = _install_fake_sdk(
        monkeypatch,
        [],
        served_models=(first_lane, second_lane),
        behavior=first_behavior,
    )
    partial = recognize_audio_to_markdown(
        slices,
        provider=[[_provider(first_lane)], [_provider(second_lane)]],
        output_path=output,
    )
    assert partial.status == "partial"
    assert set(first_fake.models.slot_calls) == {
        (first_lane, 0),
        (first_lane, 2),
        (second_lane, 1),
        (second_lane, 3),
    }

    resume_models = (
        "gemini-audio-resume-zero",
        "gemini-audio-resume-one",
        "gemini-audio-resume-two",
    )

    def resume_behavior(model: str, slot_index: int):
        return _raw_audio_response(
            f"resumed slot {slot_index} {model}",
            input_tokens=60,
            output_tokens=6,
        )

    resume_fake = _install_fake_sdk(
        monkeypatch,
        [],
        served_models=resume_models,
        behavior=resume_behavior,
    )
    resumed = resume_audio_to_markdown(
        slices,
        provider=[[_provider(model)] for model in resume_models],
        output_path=output,
    )

    assert resume_fake.models.slot_calls == [(resume_models[2], 2)]
    assert resumed.status == "complete"
    assert resumed.metadata["reused_slot_count"] == 3
    assert resumed.metadata["provider_call_count"] == 1
    assert resumed.markdown.index("initial slot 0") < resumed.markdown.index(
        "initial slot 1"
    ) < resumed.markdown.index(
        f"resumed slot 2 {resume_models[2]}"
    ) < resumed.markdown.index("initial slot 3")
    assert not (tmp_path / "resume.ocrllm-state.json").exists()
    assert first_fake.files.upload_count == first_fake.files.delete_count == 4
    assert resume_fake.files.upload_count == resume_fake.files.delete_count == 1
    assert all(not path.exists() for path in first_fake.files.upload_paths)
    assert all(not path.exists() for path in resume_fake.files.upload_paths)
    assert all(client.closed for client in first_fake.clients)
    assert all(client.closed for client in resume_fake.clients)
