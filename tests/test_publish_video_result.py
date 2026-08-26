"""Final Markdown publication for one settled video outcome."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest

from ocrllm import (
    BatchItemOutcome,
    OutputError,
    OutputExists,
    ProviderError,
    RecognitionResult,
    RetainedVideoFrame,
    VideoError,
    VideoRecognitionOutcome,
    publish_video_result,
)


def _frame(path: Path) -> RetainedVideoFrame:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"jpeg-placeholder")
    return RetainedVideoFrame(0, 0.0, path)


def _outcome(tmp_path: Path, *, partial: bool = False) -> VideoRecognitionOutcome:
    output_root = tmp_path / "artifacts"
    frame = _frame(output_root / "frames" / "frame-00000000.jpg")
    frame_result = RecognitionResult(
        markdown="Visible board text.",
        source_type="image",
        status="partial" if partial else "complete",
        metadata={
            "video_frame_indices": (0,),
            "video_frame_timestamps_seconds": (0.0,),
            "current_run_provider_call_count": 1,
        },
    )
    audio_error = (
        ProviderError(
            "Audio recognition failed.",
            details={"provider_calls_attempted": 1},
        )
        if partial
        else VideoError("No audio stream.", code="VIDEO_NO_AUDIO_STREAM")
    )
    return VideoRecognitionOutcome(
        output_root=output_root,
        retained_frames=(frame,),
        frame_outcomes=(BatchItemOutcome(index=0, result=frame_result),),
        audio_error=audio_error,
    )


@pytest.mark.parametrize(
    ("partial", "expected_status"),
    [(False, "complete"), (True, "partial")],
)
def test_publish_video_result_writes_settled_outcome_atomically(
    tmp_path: Path,
    partial: bool,
    expected_status: str,
) -> None:
    outcome = _outcome(tmp_path, partial=partial)
    target = tmp_path / "reports" / "lecture.md"

    result = publish_video_result(outcome, str(target))

    assert result.status == expected_status
    assert result.output_path == target
    assert target.read_text(encoding="utf-8") == result.markdown
    assert result.assets == tuple(frame.path for frame in outcome.retained_frames)
    assert list(target.parent.glob(".ocrllm-*.tmp")) == []


def test_publish_video_result_rejects_fully_failed_outcome_without_output(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "artifacts"
    frame = _frame(output_root / "frames" / "frame-00000000.jpg")
    outcome = VideoRecognitionOutcome(
        output_root=output_root,
        retained_frames=(frame,),
        frame_outcomes=(
            BatchItemOutcome(
                index=0,
                error=ProviderError(
                    "Frames failed.",
                    details={
                        "video_frame_indices": (0,),
                        "video_frame_timestamps_seconds": (0.0,),
                    },
                ),
            ),
        ),
        audio_error=ProviderError("Audio failed."),
    )
    target = tmp_path / "reports" / "lecture.md"

    with pytest.raises(ValueError, match="failed video outcome"):
        publish_video_result(outcome, target)

    assert not target.parent.exists()


def test_publish_video_result_rejects_existing_target_without_overwrite(
    tmp_path: Path,
) -> None:
    outcome = _outcome(tmp_path)
    target = tmp_path / "lecture.md"
    target.write_text("durable old content", encoding="utf-8")

    with pytest.raises(OutputExists):
        publish_video_result(outcome, target)

    assert target.read_text(encoding="utf-8") == "durable old content"


def test_publish_video_result_overwrites_only_after_complete_write(
    tmp_path: Path,
) -> None:
    outcome = _outcome(tmp_path)
    target = tmp_path / "lecture.md"
    target.write_text("stale", encoding="utf-8")

    result = publish_video_result(outcome, target, overwrite=True)

    assert target.read_text(encoding="utf-8") == result.markdown
    assert result.output_path == target


def test_publish_video_result_rejects_overwriting_a_retained_asset(
    tmp_path: Path,
) -> None:
    outcome = _outcome(tmp_path)
    target = outcome.retained_frames[0].path
    original_bytes = target.read_bytes()

    with pytest.raises(OutputError) as captured:
        publish_video_result(outcome, target, overwrite=True)

    assert captured.value.code == "OUTPUT_PATH_INVALID"
    assert target.read_bytes() == original_bytes


def test_publish_video_result_rejects_alias_of_retained_asset(
    tmp_path: Path,
) -> None:
    outcome = _outcome(tmp_path)
    retained_frame = outcome.retained_frames[0].path
    original_bytes = retained_frame.read_bytes()
    target = retained_frame.parent / ".." / "frames" / retained_frame.name

    with pytest.raises(OutputError) as captured:
        publish_video_result(outcome, target, overwrite=True)

    assert captured.value.code == "OUTPUT_PATH_INVALID"
    assert retained_frame.read_bytes() == original_bytes


def test_publish_video_result_rejects_hard_link_to_retained_asset(
    tmp_path: Path,
) -> None:
    outcome = _outcome(tmp_path)
    retained_frame = outcome.retained_frames[0].path
    target = tmp_path / "retained-frame-alias.md"
    os.link(retained_frame, target)

    with pytest.raises(OutputError) as captured:
        publish_video_result(outcome, target, overwrite=True)

    assert captured.value.code == "OUTPUT_PATH_INVALID"
    assert target.read_bytes() == retained_frame.read_bytes()


def test_publish_video_result_rejects_nonexistent_reserved_audio_alias(
    tmp_path: Path,
) -> None:
    outcome = _outcome(tmp_path)
    reserved_audio = outcome.output_root / "audio.mp3"
    target = outcome.output_root / "frames" / ".." / "audio.mp3"

    assert not reserved_audio.exists()
    with pytest.raises(OutputError) as captured:
        publish_video_result(outcome, target)

    assert captured.value.code == "OUTPUT_PATH_INVALID"
    assert not reserved_audio.exists()


def test_publish_video_result_preserves_retained_audio_resume_state(
    tmp_path: Path,
) -> None:
    outcome = _outcome(tmp_path, partial=True)
    state_path = outcome.output_root / ".ocrllm-video-audio-resume.json"
    original_state = b"paid interval state"
    state_path.write_bytes(original_state)

    with pytest.raises(OutputError) as captured:
        publish_video_result(outcome, state_path, overwrite=True)

    assert captured.value.code == "OUTPUT_PATH_INVALID"
    assert state_path.read_bytes() == original_state


def test_publish_video_result_write_failure_preserves_existing_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome = _outcome(tmp_path)
    target = tmp_path / "lecture.md"
    target.write_text("durable old content", encoding="utf-8")
    writer_module = importlib.import_module(
        "ocrllm.output.write_markdown_atomically"
    )

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("test-only replace failure")

    monkeypatch.setattr(writer_module.os, "replace", fail_replace)

    with pytest.raises(OutputError) as captured:
        publish_video_result(outcome, target, overwrite=True)

    assert captured.value.code == "OUTPUT_WRITE_FAILED"
    assert target.read_text(encoding="utf-8") == "durable old content"
    assert list(tmp_path.glob(".ocrllm-*.tmp")) == []
