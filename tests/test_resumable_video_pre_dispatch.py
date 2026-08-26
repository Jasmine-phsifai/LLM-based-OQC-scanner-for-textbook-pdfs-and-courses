"""Paid-slot reuse and pre-dispatch identity gates for resumable video jobs."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import shutil

import pytest

import ocrllm
from ocrllm import (
    AudioModelSettings,
    Config,
    GoogleGenAISettings,
    ProviderUnavailable,
    RecognitionPreferences,
    ResumeStateError,
    RetainedVideoFrame,
)
from ocrllm.providers.google_genai.google_genai_audio_response import (
    GoogleGenAIAudioResponse,
)

from write_test_image import write_test_image


_VALID_SHORT_MP3 = (
    Path(__file__).parent / "fixtures" / "audio" / "a1" / "mp3" / "valid_cbr.mp3"
)


class _CountingImageProvider:
    resume_identity = "resumable-video-pre-dispatch-test-v1"

    def __init__(self, *, fail_call: int | None = None) -> None:
        self.call_count = 0
        self.fail_call = fail_call

    def recognize_images(self, image_paths, *, prompt, config):
        self.call_count += 1
        if self.call_count == self.fail_call:
            raise ProviderUnavailable(
                "The test image provider is temporarily unavailable.",
                details={"provider_calls_attempted": 1},
            )
        return f"# Image pass {self.call_count}\n"


def _audio_config(tmp_path: Path, *, model: str = "test-audio-model") -> Config:
    return Config(
        provider=GoogleGenAISettings(api_key="test-only-google-key"),
        audio_model=AudioModelSettings(name=model),
        temp_dir=tmp_path / "audio-snapshots",
    )


def _install_preparation_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    source: Path,
    output_parent: Path,
) -> None:
    prepare = __import__(
        "ocrllm.video.prepare_video_media",
        fromlist=["prepare_video_media"],
    )
    extraction = __import__(
        "ocrllm.video.extract_video_audio",
        fromlist=["_extract_video_audio_from_stable_source"],
    )

    @contextmanager
    def prepare_once(_source, *, output_dir):
        assert Path(output_dir) == output_parent
        frame = RetainedVideoFrame(
            frame_index=0,
            timestamp_seconds=0.0,
            path=write_test_image(
                output_parent / source.stem / "frames" / "frame-00000000.jpg",
                color=(12, 34, 56),
            ),
        )
        yield source, (frame,)

    def extract_audio(_source, *, output_path, **_kwargs):
        target = Path(output_path)
        shutil.copyfile(_VALID_SHORT_MP3, target)
        return target

    monkeypatch.setattr(prepare, "prepare_video_media", prepare_once)
    monkeypatch.setattr(
        extraction,
        "_extract_video_audio_from_stable_source",
        extract_audio,
    )


def _patch_audio(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fail: bool,
) -> list[Path]:
    job_audio = __import__(
        "ocrllm.recognize_video_job_audio",
        fromlist=["recognize_video_job_audio"],
    )
    calls: list[Path] = []

    def recognize_audio(snapshot, *, prompt, config):
        calls.append(Path(snapshot.path))
        if fail:
            raise ProviderUnavailable(
                "The test audio provider is temporarily unavailable.",
                details={"provider_calls_attempted": 1},
            )
        return GoogleGenAIAudioResponse(
            markdown="# Audio\n",
            input_tokens=3,
            output_tokens=1,
            client_closed=True,
        )

    monkeypatch.setattr(job_audio, "recognize_short_mp3", recognize_audio)
    return calls


def test_resume_reuses_first_paid_image_pass_and_dispatches_only_missing_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "lecture.mp4"
    source.write_bytes(b"stable-test-video")
    output_parent = tmp_path / "output"
    provider = _CountingImageProvider(fail_call=2)
    image_config = Config(
        provider=provider,
        preferences=RecognitionPreferences(review_passes=1),
    )
    audio_config = _audio_config(tmp_path)
    _install_preparation_fakes(
        monkeypatch,
        source=source,
        output_parent=output_parent,
    )
    audio_calls = _patch_audio(monkeypatch, fail=False)

    with pytest.raises(ProviderUnavailable) as interrupted:
        ocrllm.recognize_video_to_markdown(
            source,
            output_dir=output_parent,
            image_config=image_config,
            audio_config=audio_config,
        )

    assert interrupted.value.details["workflow_pass"] == "review"
    assert interrupted.value.details["provider_calls_attempted"] == 3
    assert provider.call_count == 2
    # The independent audio branch settles while the image branch retains its
    # paid draft. Resume must reuse both of those durable facts.
    assert len(audio_calls) == 1
    assert not (output_parent / "lecture" / "result.md").exists()

    provider.fail_call = None
    result = ocrllm.recognize_video_to_markdown(
        source,
        output_dir=output_parent,
        image_config=image_config,
        audio_config=audio_config,
        resume=True,
    )

    assert provider.call_count == 3
    assert len(audio_calls) == 1
    assert result.output_path == output_parent / "lecture" / "result.md"
    assert "Image pass 3" in result.markdown
    # The resumed run made only the missing review call. If either the saved
    # image draft or the settled audio had been replayed, this would be larger.
    assert result.metadata["current_run_provider_call_count"] == 1


@pytest.mark.parametrize(
    "changed_fact",
    ("source", "frame", "image_config", "audio_model", "audio_artifact"),
)
def test_resume_rejects_changed_identity_before_either_provider_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_fact: str,
) -> None:
    source = tmp_path / "lecture.mp4"
    source.write_bytes(b"stable-test-video")
    output_parent = tmp_path / "output"
    output_root = output_parent / "lecture"
    provider = _CountingImageProvider()
    image_config = Config(provider=provider)
    audio_config = _audio_config(tmp_path)
    _install_preparation_fakes(
        monkeypatch,
        source=source,
        output_parent=output_parent,
    )
    initial_audio_calls = _patch_audio(monkeypatch, fail=True)

    with pytest.raises(ProviderUnavailable):
        ocrllm.recognize_video_to_markdown(
            source,
            output_dir=output_parent,
            image_config=image_config,
            audio_config=audio_config,
        )

    assert provider.call_count == 1
    assert len(initial_audio_calls) == 1

    resume_image_config = image_config
    resume_audio_config = audio_config
    if changed_fact == "source":
        source.write_bytes(b"changed-test-video")
    elif changed_fact == "frame":
        write_test_image(
            output_root / "frames" / "frame-00000000.jpg",
            color=(200, 100, 50),
        )
    elif changed_fact == "image_config":
        resume_image_config = Config(provider=provider, input_languages=("en",))
    elif changed_fact == "audio_model":
        resume_audio_config = _audio_config(tmp_path, model="changed-audio-model")
    else:
        with (output_root / "audio.mp3").open("ab") as stream:
            stream.write(b"changed")

    resumed_audio_calls = _patch_audio(monkeypatch, fail=False)
    image_calls_before_resume = provider.call_count

    with pytest.raises(ResumeStateError) as rejected:
        ocrllm.recognize_video_to_markdown(
            source,
            output_dir=output_parent,
            image_config=resume_image_config,
            audio_config=resume_audio_config,
            resume=True,
        )

    assert rejected.value.code == "RESUME_STATE_MISMATCH"
    assert provider.call_count == image_calls_before_resume
    assert resumed_audio_calls == []
    assert not (output_root / "result.md").exists()
