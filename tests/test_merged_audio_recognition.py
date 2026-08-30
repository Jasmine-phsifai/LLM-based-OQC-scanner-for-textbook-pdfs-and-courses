"""Public scalar merged-audio recognition and ordinary-resume behavior."""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from ocrllm import (
    AudioSlice,
    ProviderModel,
    recognize_audio_to_markdown,
    resume_audio_to_markdown,
    split_audio,
)
from ocrllm.errors import InvalidSource, ProviderError
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

    def upload(self, *, file):
        assert Path(file).is_file()
        self.upload_count += 1
        return SimpleNamespace(
            name=f"files/test-{self.upload_count}",
            state=SimpleNamespace(name="ACTIVE"),
        )

    def delete(self, *, name: str):
        assert name.startswith("files/test-")
        self.delete_count += 1


class _Models:
    def __init__(self, responses: list[str | Exception]) -> None:
        self.responses = responses
        self.generate_count = 0

    def list(self):
        return (
            SimpleNamespace(
                name=f"models/{MODEL}",
                supported_actions=["generateContent"],
                input_token_limit=1_048_576,
            ),
        )

    def generate_content(self, *, model: str, contents):
        assert model == MODEL
        assert type(contents[0]) is str
        self.generate_count += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return SimpleNamespace(
            text=response,
            candidates=(),
            prompt_feedback=None,
            usage_metadata=SimpleNamespace(
                prompt_token_count=100 + self.generate_count,
                candidates_token_count=10 + self.generate_count,
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

    def __init__(self, responses: list[str | Exception]) -> None:
        self.files = _Files()
        self.models = _Models(responses)
        self.clients: list[_Client] = []

    def Client(self, **_kwargs):
        client = _Client(self.files, self.models)
        self.clients.append(client)
        return client


def _provider() -> ProviderModel:
    return ProviderModel(
        vendor="google",
        model=MODEL,
        adapter_id="google_genai",
        settings=GoogleGenAISettings(api_key="test-only-google-key"),
        supports_plain_ocr=True,
        supports_detail_ocr=True,
        supports_audio=True,
        default_image_batch_size=8,
        default_audio_minutes=30,
        retry_rules={},
    )


def _install_fake_sdk(monkeypatch, responses: list[str | Exception]):
    fake = _FakeGoogleModule(responses)
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_uploaded_mp3"
    )
    short_adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_short_mp3"
    )
    monkeypatch.setattr(adapter, "load_google_genai", lambda: fake)
    monkeypatch.setattr(short_adapter, "load_google_genai", lambda: fake)
    return fake


def _write_sixty_one_second_mp3(path: Path) -> Path:
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
            "sine=frequency=440:sample_rate=16000:duration=61",
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
