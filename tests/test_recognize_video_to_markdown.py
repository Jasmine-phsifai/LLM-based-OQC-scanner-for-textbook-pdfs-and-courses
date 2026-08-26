"""Public lifecycle for one resumable video-to-Markdown job."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import inspect
from pathlib import Path
import shutil
from types import SimpleNamespace
from threading import Event

import pytest

import ocrllm
from ocrllm import (
    AudioModelSettings,
    Cancelled,
    Config,
    ConfigError,
    GoogleGenAISettings,
    NoSpeechDetected,
    OutputError,
    ProviderUnavailable,
    RecognitionResult,
    ResumeStateError,
    RetainedVideoFrame,
    VideoError,
)
from ocrllm.providers.google_genai.google_genai_audio_response import (
    GoogleGenAIAudioResponse,
)
from ocrllm.audio.build_long_audio_interval_windows import (
    build_long_audio_interval_windows,
)
from ocrllm.audio.fingerprint_long_audio_request import (
    LONG_AUDIO_REQUEST_IDENTITY_VERSION,
    fingerprint_long_audio_request,
)
from ocrllm.audio.long_audio_partial_state import (
    LONG_AUDIO_PARTIAL_STATE_VERSION,
    LongAudioPartialState,
)
from ocrllm.audio.long_audio_settled_slot import LongAudioSettledSlot
from ocrllm.build_owned_media_fingerprint import build_owned_media_fingerprint
from ocrllm.load_video_job_state import load_video_job_state
from ocrllm.processor_output import ProcessorOutput
from ocrllm.video_job_state import VideoAudioState

from write_test_image import write_test_image


_VALID_SHORT_MP3 = (
    Path(__file__).parent / "fixtures" / "audio" / "a1" / "mp3" / "valid_cbr.mp3"
)


class _ImageProvider:
    resume_identity = "resumable-video-public-test-v1"

    def __init__(self) -> None:
        self.groups: list[tuple[Path, ...]] = []

    def recognize_images(self, image_paths, *, prompt, config):
        group = tuple(image_paths)
        self.groups.append(group)
        return f"# Frame group {len(self.groups)}\n"


def _public_facade():
    try:
        return ocrllm.recognize_video_to_markdown
    except AttributeError:
        pytest.fail(
            "ocrllm.recognize_video_to_markdown is not publicly exported",
            pytrace=False,
        )


def _audio_config(tmp_path: Path, **persistence) -> Config:
    return Config(
        provider=GoogleGenAISettings(api_key="test-only-google-key"),
        audio_model=AudioModelSettings(name="test-audio-model"),
        temp_dir=tmp_path / "audio-snapshots",
        **persistence,
    )


def _root_journals(output_root: Path) -> tuple[Path, ...]:
    """Find the single opaque OCRLLM JSON sidecar without fixing its schema."""
    return tuple(
        path
        for path in output_root.iterdir()
        if path.is_file()
        and path.name.startswith(".ocrllm-")
        and path.suffix == ".json"
    )


def _install_one_frame_media(
    monkeypatch: pytest.MonkeyPatch,
    *,
    source: Path,
    output_parent: Path,
    has_audio_stream: bool,
) -> dict[str, int]:
    """Install realistic provider-free media seams with resume tripwires."""
    output_root = output_parent / source.stem
    calls = {"prepare": 0, "extract": 0}
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
        calls["prepare"] += 1
        if calls["prepare"] != 1:
            raise AssertionError("resume reselected already-journaled video frames")
        assert Path(output_dir) == output_parent
        frame = RetainedVideoFrame(
            frame_index=0,
            timestamp_seconds=0.0,
            path=write_test_image(
                output_root / "frames" / "frame-00000000.jpg",
                color=(32, 64, 96),
            ),
        )
        yield source, (frame,)

    def extract_once(_source, *, output_path, **_kwargs):
        calls["extract"] += 1
        if calls["extract"] != 1:
            raise AssertionError("resume re-extracted the journaled audio unit")
        if not has_audio_stream:
            raise VideoError(
                "The video has no audio stream.",
                code="VIDEO_NO_AUDIO_STREAM",
                details={"stage": "audio_stream_probe"},
            )
        target = Path(output_path)
        shutil.copyfile(_VALID_SHORT_MP3, target)
        return target

    monkeypatch.setattr(prepare, "prepare_video_media", prepare_once)
    monkeypatch.setattr(
        extraction,
        "_extract_video_audio_from_stable_source",
        extract_once,
    )
    return calls


def test_recognize_video_to_markdown_has_the_fixed_keyword_contract() -> None:
    signature = inspect.signature(_public_facade())

    assert tuple(signature.parameters) == (
        "source",
        "output_dir",
        "image_config",
        "audio_config",
        "audio_interval_minutes",
        "resume",
    )
    assert (
        signature.parameters["source"].kind
        is inspect.Parameter.POSITIONAL_OR_KEYWORD
    )
    for name in (
        "output_dir",
        "image_config",
        "audio_config",
        "audio_interval_minutes",
        "resume",
    ):
        assert signature.parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["audio_interval_minutes"].default is None
    assert signature.parameters["resume"].default is False


@pytest.mark.parametrize(
    ("branch", "persistence"),
    (
        ("image", {"output_dir": "branch-output"}),
        ("image", {"output_dir": "branch-output", "resume": True}),
        ("image", {"overwrite": True}),
        ("audio", {"output_dir": "branch-output"}),
        ("audio", {"output_dir": "branch-output", "resume": True}),
        ("audio", {"overwrite": True}),
    ),
)
def test_invalid_branch_persistence_stops_before_media_or_provider_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    branch: str,
    persistence: dict[str, object],
) -> None:
    prepare = __import__(
        "ocrllm.video.prepare_video_media",
        fromlist=["prepare_video_media"],
    )
    job_audio = __import__(
        "ocrllm.recognize_video_job_audio",
        fromlist=["recognize_video_job_audio"],
    )
    media_calls = 0
    audio_calls = 0

    @contextmanager
    def reject_media_work(*_args, **_kwargs):
        nonlocal media_calls
        media_calls += 1
        raise AssertionError("invalid branch persistence reached media preparation")
        yield  # pragma: no cover - makes this an explicit context manager

    def reject_audio_work(*_args, **_kwargs):
        nonlocal audio_calls
        audio_calls += 1
        raise AssertionError("invalid branch persistence reached audio recognition")

    monkeypatch.setattr(prepare, "prepare_video_media", reject_media_work)
    monkeypatch.setattr(job_audio, "recognize_short_mp3", reject_audio_work)
    image_provider = _ImageProvider()
    image_config = (
        Config(provider=image_provider, **persistence)
        if branch == "image"
        else Config(provider=image_provider)
    )
    audio_config = (
        _audio_config(tmp_path, **persistence)
        if branch == "audio"
        else _audio_config(tmp_path)
    )

    with pytest.raises(ConfigError):
        _public_facade()(
            tmp_path / "missing.mp4",
            output_dir=tmp_path / "output",
            image_config=image_config,
            audio_config=audio_config,
        )

    assert media_calls == 0
    assert audio_calls == 0
    assert image_provider.groups == []
    assert not (tmp_path / "output").exists()


def test_initial_journal_failure_removes_unpaid_output_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "journal-failure.mp4"
    source.write_bytes(b"stable-video-before-provider")
    output_parent = tmp_path / "output"
    output_root = output_parent / source.stem
    _install_one_frame_media(
        monkeypatch,
        source=source,
        output_parent=output_parent,
        has_audio_stream=True,
    )
    journal_module = __import__(
        "ocrllm.video_job_journal",
        fromlist=["VideoJobJournal"],
    )
    job_audio = __import__(
        "ocrllm.recognize_video_job_audio",
        fromlist=["recognize_video_job_audio"],
    )
    image_provider = _ImageProvider()
    audio_calls = 0

    def fail_initial_state(_self):
        raise OutputError(
            "The initial video journal could not be saved.",
            code="OUTPUT_WRITE_FAILED",
        )

    def reject_audio(*_args, **_kwargs):
        nonlocal audio_calls
        audio_calls += 1
        raise AssertionError("journal failure reached the audio provider")

    monkeypatch.setattr(
        journal_module.VideoJobJournal,
        "save_initial",
        fail_initial_state,
    )
    monkeypatch.setattr(job_audio, "recognize_short_mp3", reject_audio)

    with pytest.raises(OutputError, match="initial video journal"):
        _public_facade()(
            source,
            output_dir=output_parent,
            image_config=Config(provider=image_provider),
            audio_config=_audio_config(tmp_path),
        )

    assert not output_root.exists()
    assert image_provider.groups == []
    assert audio_calls == 0


def test_recoverable_audio_gap_keeps_one_journal_and_resume_reuses_images(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "lecture.mp4"
    source.write_bytes(b"stable-test-video")
    output_parent = tmp_path / "output"
    output_root = output_parent / "lecture"
    image_provider = _ImageProvider()
    prepare_calls = 0
    extraction_calls = 0
    audio_calls = 0

    prepare = __import__(
        "ocrllm.video.prepare_video_media",
        fromlist=["prepare_video_media"],
    )
    extraction = __import__(
        "ocrllm.video.extract_video_audio",
        fromlist=["_extract_video_audio_from_stable_source"],
    )
    job_audio = __import__(
        "ocrllm.recognize_video_job_audio",
        fromlist=["recognize_video_job_audio"],
    )

    @contextmanager
    def prepare_once(_source, *, output_dir):
        nonlocal prepare_calls
        prepare_calls += 1
        if prepare_calls != 1:
            raise AssertionError("resume reselected already-journaled video frames")
        assert Path(output_dir) == output_parent
        frames_dir = output_root / "frames"
        frames = tuple(
            RetainedVideoFrame(
                frame_index=index * 10,
                timestamp_seconds=float(index),
                path=write_test_image(
                    frames_dir / f"frame-{index:08d}.jpg",
                    color=(index, 0, 0),
                ),
            )
            for index in range(9)
        )
        yield source, frames

    def extract_once(_source, *, output_path, **_kwargs):
        nonlocal extraction_calls
        extraction_calls += 1
        if extraction_calls != 1:
            raise AssertionError("resume re-extracted the retained audio artifact")
        target = Path(output_path)
        shutil.copyfile(_VALID_SHORT_MP3, target)
        return target

    def recognize_audio(_snapshot, *, prompt, config):
        nonlocal audio_calls
        audio_calls += 1
        if audio_calls == 1:
            raise ProviderUnavailable(
                "Audio provider is temporarily unavailable.",
                details={"provider_calls_attempted": 1},
            )
        return GoogleGenAIAudioResponse(
            markdown="# Audio\n",
            input_tokens=7,
            output_tokens=2,
            client_closed=True,
        )

    monkeypatch.setattr(prepare, "prepare_video_media", prepare_once)
    monkeypatch.setattr(
        extraction,
        "_extract_video_audio_from_stable_source",
        extract_once,
    )
    monkeypatch.setattr(job_audio, "recognize_short_mp3", recognize_audio)
    facade = _public_facade()
    image_config = Config(provider=image_provider)
    audio_config = _audio_config(tmp_path)

    with pytest.raises(ProviderUnavailable) as captured:
        facade(
            source,
            output_dir=output_parent,
            image_config=image_config,
            audio_config=audio_config,
        )

    assert captured.value.details["provider_calls_attempted"] == 1
    assert [len(group) for group in image_provider.groups] == [8, 1]
    assert prepare_calls == extraction_calls == audio_calls == 1
    assert output_root.is_dir()
    assert len(_root_journals(output_root)) == 1
    assert not (output_root / "result.md").exists()

    settled_image_groups = tuple(image_provider.groups)
    result = facade(
        source,
        output_dir=output_parent,
        image_config=image_config,
        audio_config=audio_config,
        resume=True,
    )

    assert type(result) is RecognitionResult
    assert result.source_type == "video"
    assert "Frame group 1" in result.markdown
    assert "Frame group 2" in result.markdown
    assert "Audio" in result.markdown
    assert result.output_path == output_root / "result.md"
    assert result.output_path.read_text(encoding="utf-8") == result.markdown
    assert tuple(image_provider.groups) == settled_image_groups
    assert prepare_calls == 1
    assert extraction_calls == 1
    assert audio_calls == 2
    assert _root_journals(output_root) == ()


def test_no_audio_stream_is_terminal_and_publishes_without_audio_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "silent-lecture.mp4"
    source.write_bytes(b"stable-video-without-audio")
    output_parent = tmp_path / "output"
    output_root = output_parent / source.stem
    media_calls = _install_one_frame_media(
        monkeypatch,
        source=source,
        output_parent=output_parent,
        has_audio_stream=False,
    )
    job_audio = __import__(
        "ocrllm.recognize_video_job_audio",
        fromlist=["recognize_video_job_audio"],
    )
    audio_calls = 0

    def reject_audio_dispatch(*_args, **_kwargs):
        nonlocal audio_calls
        audio_calls += 1
        raise AssertionError("an absent audio stream reached the provider")

    monkeypatch.setattr(job_audio, "recognize_short_mp3", reject_audio_dispatch)
    image_provider = _ImageProvider()
    result = _public_facade()(
        source,
        output_dir=output_parent,
        image_config=Config(provider=image_provider),
        audio_config=_audio_config(tmp_path),
    )

    assert type(result) is RecognitionResult
    assert result.status == "complete"
    assert result.metadata["audio_state"] == "absent"
    assert "No audio stream was present." in result.markdown
    assert result.output_path == output_root / "result.md"
    assert result.output_path.read_text(encoding="utf-8") == result.markdown
    assert audio_calls == 0
    assert media_calls == {"prepare": 1, "extract": 1}
    assert len(image_provider.groups) == 1
    assert _root_journals(output_root) == ()


@pytest.mark.parametrize("client_closed", [True, False])
def test_no_speech_state_survives_publication_failure_and_resume_uses_zero_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client_closed: bool,
) -> None:
    source = tmp_path / "quiet-lecture.mp4"
    source.write_bytes(b"stable-video-with-quiet-audio")
    output_parent = tmp_path / "output"
    output_root = output_parent / source.stem
    media_calls = _install_one_frame_media(
        monkeypatch,
        source=source,
        output_parent=output_parent,
        has_audio_stream=True,
    )
    job_audio = __import__(
        "ocrllm.recognize_video_job_audio",
        fromlist=["recognize_video_job_audio"],
    )
    finalizer = __import__(
        "ocrllm.finalize_video_job",
        fromlist=["publish_video_result"],
    )
    audio_calls = 0
    publication_calls = 0
    real_publish = finalizer.publish_video_result

    def no_speech(_snapshot, *, prompt, config):
        nonlocal audio_calls
        audio_calls += 1
        raise NoSpeechDetected(
            details={
                "provider_calls_attempted": 1,
                "provider_client_closed": client_closed,
            }
        )

    def fail_first_publication(outcome, output_path, *, overwrite=False):
        nonlocal publication_calls
        publication_calls += 1
        if publication_calls == 1:
            raise OutputError(
                "The final video Markdown could not be published.",
                code="OUTPUT_WRITE_FAILED",
            )
        return real_publish(outcome, output_path, overwrite=overwrite)

    monkeypatch.setattr(job_audio, "recognize_short_mp3", no_speech)
    monkeypatch.setattr(finalizer, "publish_video_result", fail_first_publication)
    image_provider = _ImageProvider()
    image_config = Config(provider=image_provider)
    audio_config = _audio_config(tmp_path)

    with pytest.raises(OutputError, match="could not be published"):
        _public_facade()(
            source,
            output_dir=output_parent,
            image_config=image_config,
            audio_config=audio_config,
        )

    assert audio_calls == publication_calls == 1
    assert media_calls == {"prepare": 1, "extract": 1}
    assert len(image_provider.groups) == 1
    journals = _root_journals(output_root)
    assert len(journals) == 1
    saved = load_video_job_state(journals[0]).audio.short_state
    assert saved is not None
    assert saved.metadata == {
        "provider": "google",
        "model": "test-audio-model",
        "provider_call_count": 1,
        "provider_client_closed": client_closed,
    }
    assert "remote_file_deleted" not in saved.metadata
    assert saved.warnings == (
        ("No recognizable speech was detected.",)
        if client_closed
        else (
            "No recognizable speech was detected.",
            "The Google GenAI client could not be closed after recognition.",
        )
    )
    assert not (output_root / "result.md").exists()

    result = _public_facade()(
        source,
        output_dir=output_parent,
        image_config=image_config,
        audio_config=audio_config,
        resume=True,
    )

    assert result.status == "partial"
    assert result.metadata["audio_error_code"] == "NO_SPEECH_DETECTED"
    assert result.metadata["current_run_provider_call_count"] == 0
    assert "NO_SPEECH_DETECTED" in result.markdown
    cleanup_warning = (
        "The Google GenAI client could not be closed after recognition."
    )
    if client_closed:
        assert cleanup_warning not in result.warnings
        assert "audio_provider_client_closed" not in result.metadata
    else:
        assert cleanup_warning in result.warnings
        assert result.metadata["audio_provider_client_closed"] is False
    assert result.output_path == output_root / "result.md"
    assert audio_calls == 1
    assert publication_calls == 2
    assert media_calls == {"prepare": 1, "extract": 1}
    assert len(image_provider.groups) == 1
    assert _root_journals(output_root) == ()


def test_published_result_and_journal_resume_cleanup_reuses_every_provider_unit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "published-lecture.mp4"
    source.write_bytes(b"stable-video-for-coexistence")
    output_parent = tmp_path / "output"
    output_root = output_parent / source.stem
    media_calls = _install_one_frame_media(
        monkeypatch,
        source=source,
        output_parent=output_parent,
        has_audio_stream=True,
    )
    job_audio = __import__(
        "ocrllm.recognize_video_job_audio",
        fromlist=["recognize_video_job_audio"],
    )
    audio_calls = 0

    def recognize_audio(_snapshot, *, prompt, config):
        nonlocal audio_calls
        audio_calls += 1
        return GoogleGenAIAudioResponse(
            markdown="# Audio\n",
            input_tokens=7,
            output_tokens=2,
            client_closed=True,
        )

    monkeypatch.setattr(job_audio, "recognize_short_mp3", recognize_audio)
    image_provider = _ImageProvider()
    image_config = Config(provider=image_provider)
    audio_config = _audio_config(tmp_path)
    original_unlink = Path.unlink

    def keep_root_journal(path: Path, *args, **kwargs):
        if (
            path.parent == output_root
            and path.name.startswith(".ocrllm-")
            and path.suffix == ".json"
        ):
            raise PermissionError("injected video journal cleanup failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", keep_root_journal)
    first = _public_facade()(
        source,
        output_dir=output_parent,
        image_config=image_config,
        audio_config=audio_config,
    )

    assert first.status == "partial"
    assert first.metadata["resume_state_removed"] is False
    assert first.output_path == output_root / "result.md"
    assert first.output_path.read_text(encoding="utf-8") == first.markdown
    assert len(_root_journals(output_root)) == 1
    assert audio_calls == 1
    assert len(image_provider.groups) == 1

    original_bytes = first.output_path.read_bytes()
    first.output_path.write_bytes(b"# changed result\n")
    with pytest.raises(ResumeStateError) as mismatch:
        _public_facade()(
            source,
            output_dir=output_parent,
            image_config=image_config,
            audio_config=audio_config,
            resume=True,
        )
    assert mismatch.value.code == "RESUME_STATE_MISMATCH"
    assert audio_calls == 1
    assert len(image_provider.groups) == 1
    first.output_path.write_bytes(original_bytes)

    monkeypatch.setattr(Path, "unlink", original_unlink)
    resumed = _public_facade()(
        source,
        output_dir=output_parent,
        image_config=image_config,
        audio_config=audio_config,
        resume=True,
    )

    assert resumed.status == "complete"
    assert resumed.output_path == first.output_path
    assert resumed.markdown == first.markdown
    assert resumed.metadata["current_run_provider_call_count"] == 0
    assert audio_calls == 1
    assert media_calls == {"prepare": 1, "extract": 1}
    assert len(image_provider.groups) == 1
    assert _root_journals(output_root) == ()


@pytest.mark.parametrize(
    ("mode", "interval_minutes"),
    (("whole", None), ("interval", 5)),
)
def test_long_audio_modes_resume_from_the_single_video_journal_after_publish_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    interval_minutes: int | None,
) -> None:
    source = tmp_path / f"{mode}-lecture.mp4"
    source.write_bytes(f"stable-{mode}-video".encode("ascii"))
    output_parent = tmp_path / "output"
    output_root = output_parent / source.stem
    media_calls = _install_one_frame_media(
        monkeypatch,
        source=source,
        output_parent=output_parent,
        has_audio_stream=True,
    )
    preparation = __import__(
        "ocrllm.prepare_video_job_audio_state",
        fromlist=["prepare_video_job_audio_state"],
    )
    resume_validation = __import__(
        "ocrllm.validate_video_job_resume",
        fromlist=["prepare_video_job_audio_state"],
    )
    job_audio = __import__(
        "ocrllm.recognize_video_job_audio",
        fromlist=["recognize_video_job_audio"],
    )
    finalizer = __import__(
        "ocrllm.finalize_video_job",
        fromlist=["publish_video_result"],
    )
    duration_seconds = 601.0
    provider_calls = 0
    processor_calls = 0
    publication_calls = 0
    real_publish = finalizer.publish_video_result

    def ready_audio(artifact: Path, *, config, interval_minutes):
        raw = artifact.read_bytes()
        assert interval_minutes == (5 if mode == "interval" else None)
        return VideoAudioState(
            state="ready",
            mode=mode,
            interval_minutes=interval_minutes,
            model=config.audio_model.name,
            artifact=build_owned_media_fingerprint(
                artifact,
                byte_size=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(),
            ),
            duration_seconds=duration_seconds,
        )

    @contextmanager
    def stable_audio_snapshot(artifact: Path, **_kwargs):
        raw = artifact.read_bytes()
        yield SimpleNamespace(
            path=artifact,
            byte_size=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),
            duration_seconds=duration_seconds,
        )

    def settle_long_audio(
        snapshot,
        *,
        config,
        persist_state,
        saved_state,
        interval_minutes=None,
    ):
        nonlocal provider_calls, processor_calls
        processor_calls += 1
        assert interval_minutes == (5 if mode == "interval" else None)
        if mode == "whole":
            fingerprints = (
                fingerprint_long_audio_request(
                    source_sha256=snapshot.sha256,
                    mode="whole",
                    provider="google",
                    model=config.audio_model.name,
                    transport="google_files",
                ),
            )
        else:
            fingerprints = tuple(
                fingerprint_long_audio_request(
                    source_sha256=snapshot.sha256,
                    mode="interval",
                    provider="google",
                    model=config.audio_model.name,
                    transport="google_files",
                    window=window,
                )
                for window in build_long_audio_interval_windows(
                    duration_seconds=snapshot.duration_seconds,
                    interval_minutes=5,
                )
            )
        markdown = f"# {mode.title()} audio\n"
        slots = tuple(
            LongAudioSettledSlot(
                window_index=index,
                request_fingerprint=fingerprint,
                markdown=markdown,
                markdown_sha256=hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
                provider="google",
                model=config.audio_model.name,
                transport="google_files",
                provider_calls_attempted=1,
                input_tokens=10 + index,
                output_tokens=2,
                status="complete",
                warnings=(),
                provider_file_cleanup_succeeded=True,
                provider_client_cleanup_succeeded=True,
            )
            for index, fingerprint in enumerate(fingerprints)
        )
        state = LongAudioPartialState(
            state_version=LONG_AUDIO_PARTIAL_STATE_VERSION,
            identity_version=LONG_AUDIO_REQUEST_IDENTITY_VERSION,
            mode=mode,
            interval_minutes=interval_minutes,
            request_fingerprints=fingerprints,
            slots=slots,
        )
        if saved_state is None:
            provider_calls += len(slots)
            persist_state(state)
            current_calls = len(slots)
        else:
            assert saved_state == state
            current_calls = 0
        return ProcessorOutput(
            media_type="audio",
            markdown="\n\n".join(slot.markdown.strip() for slot in slots),
            metadata={
                "provider": "google",
                "model": config.audio_model.name,
                "transport": "google_files",
                "provider_call_count": len(slots),
                "current_run_provider_call_count": current_calls,
                "current_model_token_usage": (),
                "remote_file_deleted": True,
                "provider_client_closed": True,
            },
        ), current_calls

    def fail_first_publication(outcome, output_path, *, overwrite=False):
        nonlocal publication_calls
        publication_calls += 1
        if publication_calls == 1:
            raise OutputError(
                "The final video Markdown could not be published.",
                code="OUTPUT_WRITE_FAILED",
            )
        return real_publish(outcome, output_path, overwrite=overwrite)

    monkeypatch.setattr(preparation, "prepare_video_job_audio_state", ready_audio)
    monkeypatch.setattr(
        resume_validation,
        "prepare_video_job_audio_state",
        ready_audio,
    )
    monkeypatch.setattr(job_audio, "snapshot_video_mp3", stable_audio_snapshot)
    processor_name = (
        "recognize_long_mp3_whole"
        if mode == "whole"
        else "recognize_long_mp3_intervals"
    )
    monkeypatch.setattr(job_audio, processor_name, settle_long_audio)
    monkeypatch.setattr(finalizer, "publish_video_result", fail_first_publication)
    image_provider = _ImageProvider()
    kwargs = (
        {}
        if interval_minutes is None
        else {"audio_interval_minutes": interval_minutes}
    )

    with pytest.raises(OutputError, match="could not be published"):
        _public_facade()(
            source,
            output_dir=output_parent,
            image_config=Config(provider=image_provider),
            audio_config=_audio_config(tmp_path),
            **kwargs,
        )

    assert provider_calls > 0
    calls_after_settlement = provider_calls
    assert processor_calls == publication_calls == 1
    assert media_calls == {"prepare": 1, "extract": 1}
    assert len(_root_journals(output_root)) == 1
    assert not (output_root / "result.md").exists()
    assert not tuple(output_root.rglob(".ocrllm-long-audio-resume.json"))
    assert not tuple(output_root.rglob(".ocrllm-video-audio-resume.json"))

    if interval_minutes is not None:
        with pytest.raises(ResumeStateError) as mismatch:
            _public_facade()(
                source,
                output_dir=output_parent,
                image_config=Config(provider=image_provider),
                audio_config=_audio_config(tmp_path),
                audio_interval_minutes=interval_minutes + 1,
                resume=True,
            )
        assert mismatch.value.code == "RESUME_STATE_MISMATCH"
        assert provider_calls == calls_after_settlement
        assert processor_calls == publication_calls == 1

    result = _public_facade()(
        source,
        output_dir=output_parent,
        image_config=Config(provider=image_provider),
        audio_config=_audio_config(tmp_path),
        resume=True,
    )

    assert result.output_path == output_root / "result.md"
    assert result.output_path.read_text(encoding="utf-8") == result.markdown
    assert result.metadata["current_run_provider_call_count"] == 0
    assert provider_calls == calls_after_settlement
    assert processor_calls == publication_calls == 2
    assert media_calls == {"prepare": 1, "extract": 1}
    assert len(image_provider.groups) == 1
    assert _root_journals(output_root) == ()
    assert not tuple(output_root.rglob(".ocrllm-long-audio-resume.json"))
    assert not tuple(output_root.rglob(".ocrllm-video-audio-resume.json"))


def test_relative_output_directory_resumes_against_one_canonical_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "relative-lecture.mp4"
    source.write_bytes(b"stable-relative-video")
    output_parent = tmp_path / "relative-output"
    output_root = output_parent / source.stem
    _install_one_frame_media(
        monkeypatch,
        source=source,
        output_parent=output_parent,
        has_audio_stream=True,
    )
    monkeypatch.chdir(tmp_path)
    job_audio = __import__(
        "ocrllm.recognize_video_job_audio",
        fromlist=["recognize_video_job_audio"],
    )
    audio_calls = 0

    def recognize_audio(_snapshot, *, prompt, config):
        nonlocal audio_calls
        audio_calls += 1
        if audio_calls == 1:
            raise ProviderUnavailable(
                "The audio provider is temporarily unavailable.",
                details={"provider_calls_attempted": 1},
            )
        return GoogleGenAIAudioResponse(
            markdown="# Audio\n",
            input_tokens=2,
            output_tokens=1,
            client_closed=True,
        )

    monkeypatch.setattr(job_audio, "recognize_short_mp3", recognize_audio)
    image_provider = _ImageProvider()
    image_config = Config(provider=image_provider)
    audio_config = _audio_config(tmp_path)

    with pytest.raises(ProviderUnavailable):
        _public_facade()(
            source,
            output_dir=Path("relative-output"),
            image_config=image_config,
            audio_config=audio_config,
        )

    result = _public_facade()(
        source,
        output_dir=Path("relative-output"),
        image_config=image_config,
        audio_config=audio_config,
        resume=True,
    )

    assert result.output_path == output_root / "result.md"
    assert result.output_path.is_absolute()
    assert len(image_provider.groups) == 1
    assert audio_calls == 2


@pytest.mark.parametrize("cancelled_branch", ("image", "audio"))
def test_one_pre_cancelled_branch_preserves_other_branch_settlement_for_resume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cancelled_branch: str,
) -> None:
    source = tmp_path / f"cancelled-{cancelled_branch}.mp4"
    source.write_bytes(b"stable-cancellation-video")
    output_parent = tmp_path / "output"
    output_root = output_parent / source.stem
    _install_one_frame_media(
        monkeypatch,
        source=source,
        output_parent=output_parent,
        has_audio_stream=True,
    )
    job_audio = __import__(
        "ocrllm.recognize_video_job_audio",
        fromlist=["recognize_video_job_audio"],
    )
    audio_calls = 0

    def recognize_audio(_snapshot, *, prompt, config):
        nonlocal audio_calls
        audio_calls += 1
        return GoogleGenAIAudioResponse(
            markdown="# Audio\n",
            input_tokens=2,
            output_tokens=1,
            client_closed=True,
        )

    monkeypatch.setattr(job_audio, "recognize_short_mp3", recognize_audio)
    cancellation = Event()
    cancellation.set()
    image_provider = _ImageProvider()
    image_config = Config(
        provider=image_provider,
        cancellation=cancellation if cancelled_branch == "image" else None,
    )
    audio_config = _audio_config(
        tmp_path,
        cancellation=cancellation if cancelled_branch == "audio" else None,
    )

    with pytest.raises(Cancelled):
        _public_facade()(
            source,
            output_dir=output_parent,
            image_config=image_config,
            audio_config=audio_config,
        )

    assert len(_root_journals(output_root)) == 1
    assert len(image_provider.groups) == (0 if cancelled_branch == "image" else 1)
    assert audio_calls == (1 if cancelled_branch == "image" else 0)

    cancellation.clear()
    result = _public_facade()(
        source,
        output_dir=output_parent,
        image_config=image_config,
        audio_config=audio_config,
        resume=True,
    )

    assert result.output_path == output_root / "result.md"
    assert len(image_provider.groups) == 1
    assert audio_calls == 1
    assert _root_journals(output_root) == ()
