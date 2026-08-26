"""Strict serialization and durable I/O for one resumable video job."""

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path

import pytest

from ocrllm.audio.fingerprint_long_audio_request import (
    LONG_AUDIO_REQUEST_IDENTITY_VERSION,
)
from ocrllm.audio.long_audio_partial_state import (
    LONG_AUDIO_PARTIAL_STATE_VERSION,
    LongAudioPartialState,
)
from ocrllm.audio.long_audio_settled_slot import LongAudioSettledSlot
from ocrllm.contracts.source_fingerprint import SourceFingerprint
from ocrllm.errors import OutputError, ResumeStateError
from ocrllm.fingerprint_image_request import IMAGE_REQUEST_IDENTITY_VERSION
from ocrllm.image_request_identity import ImageRequestIdentity
from ocrllm.image_resume_state import IMAGE_RESUME_STATE_VERSION, ImageResumeState
from ocrllm.parse_video_job_state import parse_video_job_state
from ocrllm.serialize_video_job_state import serialize_video_job_state
from ocrllm.video_job_state import (
    VIDEO_JOB_STATE_VERSION,
    VideoAudioState,
    VideoFrameGroupState,
    VideoJobState,
)


loader = importlib.import_module("ocrllm.load_video_job_state")
saver = importlib.import_module("ocrllm.save_video_job_state_atomically")


def _source(uri: str, marker: str, byte_size: int = 12) -> SourceFingerprint:
    return SourceFingerprint(uri=uri, byte_size=byte_size, sha256=marker * 64)


def _image_group(
    *,
    index: int,
    frame_index: int,
    timestamp: float,
    marker: str,
    settled: bool,
) -> VideoFrameGroupState:
    source = _source(
        f"file:///video-job/frames/frame-{frame_index:06d}.png",
        marker,
    )
    request_fingerprint = marker * 64
    identity = ImageRequestIdentity(
        request_fingerprint=request_fingerprint,
        identity_version=IMAGE_REQUEST_IDENTITY_VERSION,
        processor_name="test.video.frames",
        processor_version="test.video.frames.v1",
        sources=(source,),
    )
    markdown = f"## Frame {frame_index}\n"
    image_state = (
        ImageResumeState(
            state_version=IMAGE_RESUME_STATE_VERSION,
            identity_version=identity.identity_version,
            request_fingerprint=identity.request_fingerprint,
            processor_name=identity.processor_name,
            processor_version=identity.processor_version,
            sources=identity.sources,
            markdown=markdown,
            media_type="image",
            profile="board",
            status="complete",
            hotwords=("LaTeX",),
            warnings=(),
            metadata={"provider_calls_attempted": 1, "note": "完整画面"},
            final_markdown_sha256=hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
        )
        if settled
        else None
    )
    return VideoFrameGroupState(
        index=index,
        frame_indices=(frame_index,),
        frame_timestamps_seconds=(timestamp,),
        identity=identity,
        image_state=image_state,
    )


def _long_audio_state() -> LongAudioPartialState:
    request_fingerprint = "d" * 64
    markdown = "## Audio\nA bounded transcript.\n"
    slot = LongAudioSettledSlot(
        window_index=0,
        request_fingerprint=request_fingerprint,
        markdown=markdown,
        markdown_sha256=hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
        provider="google",
        model="gemini-test",
        transport="google_files",
        provider_calls_attempted=1,
        input_tokens=120,
        output_tokens=18,
        status="complete",
        warnings=(),
        provider_file_cleanup_succeeded=True,
        provider_client_cleanup_succeeded=True,
    )
    return LongAudioPartialState(
        state_version=LONG_AUDIO_PARTIAL_STATE_VERSION,
        identity_version=LONG_AUDIO_REQUEST_IDENTITY_VERSION,
        mode="interval",
        interval_minutes=10,
        request_fingerprints=(request_fingerprint,),
        slots=(slot,),
    )


def _state() -> VideoJobState:
    return VideoJobState(
        state_version=VIDEO_JOB_STATE_VERSION,
        source=_source("file:///source/lecture.mp4", "a", byte_size=4096),
        frame_groups=(
            _image_group(
                index=0,
                frame_index=0,
                timestamp=0.0,
                marker="b",
                settled=True,
            ),
            _image_group(
                index=1,
                frame_index=8,
                timestamp=80.0,
                marker="c",
                settled=True,
            ),
        ),
        audio=VideoAudioState(
            state="ready",
            mode="interval",
            interval_minutes=10,
            model="gemini-test",
            artifact=_source("file:///video-job/audio.mp3", "e", byte_size=1024),
            duration_seconds=601.5,
            long_state=_long_audio_state(),
        ),
        final_markdown_sha256="f" * 64,
    )


def _document() -> dict[str, object]:
    return json.loads(serialize_video_job_state(_state()).decode("utf-8"))


def test_canonical_round_trip_embeds_image_and_long_audio_state() -> None:
    state = _state()

    first = serialize_video_job_state(state)
    parsed = parse_video_job_state(first)

    assert first == serialize_video_job_state(state)
    assert first.endswith(b"\n")
    assert b": " not in first
    assert b", " not in first
    assert parsed == state
    assert parsed.frame_groups[0].image_state == state.frame_groups[0].image_state
    assert parsed.audio.long_state == state.audio.long_state
    assert serialize_video_job_state(parsed) == first


def test_parser_rejects_duplicate_keys() -> None:
    valid = serialize_video_job_state(_state()).decode("utf-8")
    duplicate = valid.replace(
        '"state_version":"ocrllm.video-job.v1"',
        '"state_version":"ocrllm.video-job.v1",'
        '"state_version":"ocrllm.video-job.v1"',
        1,
    )

    with pytest.raises(ResumeStateError) as caught:
        parse_video_job_state(duplicate.encode("utf-8"))

    assert caught.value.code == "RESUME_STATE_INVALID"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda document: document.__setitem__("unexpected", True),
        lambda document: document["frame_groups"][0].__setitem__(
            "unexpected", True
        ),
        lambda document: document["frame_groups"][0]["image_state"].__setitem__(
            "final_markdown_sha256", "not-a-sha256"
        ),
        lambda document: document["audio"]["long_state"]["slots"][0].__setitem__(
            "markdown_sha256", "0" * 64
        ),
    ],
    ids=("root-schema", "group-schema", "nested-image", "nested-long-audio"),
)
def test_parser_rejects_schema_drift_and_corrupt_nested_state(mutate) -> None:
    document = _document()
    mutate(document)

    with pytest.raises(ResumeStateError) as caught:
        parse_video_job_state(json.dumps(document).encode("utf-8"))

    assert caught.value.code == "RESUME_STATE_INVALID"


def test_parser_rejects_nonfinite_values() -> None:
    valid = serialize_video_job_state(_state())
    nonfinite = valid.replace(b'"duration_seconds":601.5', b'"duration_seconds":NaN')

    with pytest.raises(ResumeStateError) as caught:
        parse_video_job_state(nonfinite)

    assert caught.value.code == "RESUME_STATE_INVALID"


def test_parser_rejects_final_digest_before_every_unit_is_settled() -> None:
    document = _document()
    document["frame_groups"][1]["image_state"] = None

    with pytest.raises(ResumeStateError) as caught:
        parse_video_job_state(json.dumps(document).encode("utf-8"))

    assert caught.value.code == "RESUME_STATE_INVALID"


def test_parser_rejects_decreasing_frame_timestamps() -> None:
    document = _document()
    document["frame_groups"][0]["frame_timestamps_seconds"] = [81.0]

    with pytest.raises(ResumeStateError) as caught:
        parse_video_job_state(json.dumps(document).encode("utf-8"))

    assert caught.value.code == "RESUME_STATE_INVALID"


def test_loader_bounds_the_actual_read_after_a_small_stat(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_path = tmp_path / ".ocrllm-video-resume.json"
    state_path.write_bytes(b"12345678")
    real_open = Path.open
    monkeypatch.setattr(loader, "VIDEO_JOB_STATE_MAX_BYTES", 8)

    class GrowingReader:
        def __init__(self, wrapped) -> None:
            self.wrapped = wrapped

        def __getattr__(self, name):
            return getattr(self.wrapped, name)

        def read(self, size: int = -1) -> bytes:
            assert size == 9
            return b"123456789"

    def grow_after_stat(path: Path, *args, **kwargs):
        opened = real_open(path, *args, **kwargs)
        mode = args[0] if args else kwargs.get("mode", "r")
        if path == state_path and mode == "rb":
            return GrowingReader(opened)
        return opened

    monkeypatch.setattr(Path, "open", grow_after_stat)

    with pytest.raises(ResumeStateError) as caught:
        loader.load_video_job_state(state_path)

    assert caught.value.code == "RESUME_STATE_INVALID"


def test_save_replaces_old_state_only_after_complete_sibling_write(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_path = tmp_path / ".ocrllm-video-resume.json"
    state_path.write_bytes(b"durable old state")
    expected = serialize_video_job_state(_state())
    real_replace = saver.os.replace
    inspected = False

    def inspect_then_replace(temporary_path: Path, target_path: Path) -> None:
        nonlocal inspected
        inspected = True
        assert target_path == state_path
        assert temporary_path.parent == state_path.parent
        assert temporary_path.name.startswith(".ocrllm-")
        assert temporary_path.suffix == ".tmp"
        assert state_path.read_bytes() == b"durable old state"
        assert temporary_path.read_bytes() == expected
        real_replace(temporary_path, target_path)

    monkeypatch.setattr(saver.os, "replace", inspect_then_replace)

    saver.save_video_job_state_atomically(state_path, _state())

    assert inspected is True
    assert state_path.read_bytes() == expected
    assert loader.load_video_job_state(state_path) == _state()
    assert list(tmp_path.glob(".ocrllm-*.tmp")) == []


def test_replace_failure_preserves_the_last_durable_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_path = tmp_path / ".ocrllm-video-resume.json"
    state_path.write_bytes(b"durable old state")

    def fail_replace(_temporary_path: Path, _target_path: Path) -> None:
        raise OSError("private replacement detail")

    monkeypatch.setattr(saver.os, "replace", fail_replace)

    with pytest.raises(OutputError) as caught:
        saver.save_video_job_state_atomically(state_path, _state())

    assert caught.value.code == "OUTPUT_WRITE_FAILED"
    assert "private replacement detail" not in str(caught.value)
    assert state_path.read_bytes() == b"durable old state"
    assert list(tmp_path.glob(".ocrllm-*.tmp")) == []
