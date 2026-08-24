"""Composition contract for already-settled video recognition branches."""

from __future__ import annotations

from pathlib import Path

import pytest

from ocrllm import (
    BatchItemOutcome,
    OutputError,
    ProviderError,
    RecognitionResult,
    RetainedVideoFrame,
    VideoError,
    VideoRecognitionOutcome,
    compose_video_result,
)


def _frame(path: Path, index: int, timestamp: float) -> RetainedVideoFrame:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"jpeg-placeholder")
    return RetainedVideoFrame(index, timestamp, path)


def _frame_result(
    *,
    markdown: str,
    indices: tuple[int, ...],
    timestamps: tuple[float, ...],
    model: str = "vision-model",
) -> RecognitionResult:
    return RecognitionResult(
        markdown=markdown,
        source_type="image",
        metadata={
            "video_frame_indices": indices,
            "video_frame_timestamps_seconds": timestamps,
            "current_run_provider_call_count": 1,
            "current_model_token_usage": (
                {"model": model, "input_tokens": 10, "output_tokens": 2},
            ),
        },
    )


def _audio_result() -> RecognitionResult:
    return RecognitionResult(
        markdown="Audio transcript.",
        source_type="audio",
        metadata={
            "provider_call_count": 1,
            "current_model_token_usage": (
                {"model": "audio-model", "input_tokens": 20, "output_tokens": 4},
            ),
        },
    )


def test_compose_video_result_keeps_frames_and_audio_separate(tmp_path: Path) -> None:
    first = _frame(tmp_path / "video" / "frames" / "frame-1.jpg", 0, 0.0)
    second = _frame(tmp_path / "video" / "frames" / "frame-2.jpg", 10, 5.0)
    audio = tmp_path / "video" / "audio.mp3"
    audio.write_bytes(b"mp3-placeholder")
    outcome = VideoRecognitionOutcome(
        output_root=tmp_path / "video",
        retained_frames=(first, second),
        frame_outcomes=(
            BatchItemOutcome(
                index=0,
                result=_frame_result(
                    markdown="First board.",
                    indices=(0,),
                    timestamps=(0.0,),
                ),
            ),
            BatchItemOutcome(
                index=1,
                result=_frame_result(
                    markdown="Second board.",
                    indices=(10,),
                    timestamps=(5.0,),
                ),
            ),
        ),
        audio_artifact=audio,
        audio_result=_audio_result(),
    )

    result = compose_video_result(outcome)

    assert type(result) is RecognitionResult
    assert result.source_type == "video"
    assert result.status == "complete"
    assert result.output_path is None
    assert result.assets == (first.path, second.path, audio)
    assert result.markdown == (
        "# Video frames\n\n"
        "## Retained frame group 1\n\n"
        "Frame indices: `0`  \n"
        "Timestamps (seconds): `0.0`\n\n"
        "First board.\n\n"
        "## Retained frame group 2\n\n"
        "Frame indices: `10`  \n"
        "Timestamps (seconds): `5.0`\n\n"
        "Second board.\n\n"
        "# Video audio\n\n"
        "Audio transcript.\n"
    )
    assert result.metadata["video_frame_count"] == 2
    assert result.metadata["video_frame_group_count"] == 2
    assert result.metadata["successful_video_frame_group_count"] == 2
    assert result.metadata["failed_video_frame_group_count"] == 0
    assert result.metadata["audio_state"] == "recognized"
    assert result.metadata["current_run_provider_call_count"] == 3
    assert result.metadata["current_model_token_usage"] == (
        {"model": "vision-model", "input_tokens": 20, "output_tokens": 4},
        {"model": "audio-model", "input_tokens": 20, "output_tokens": 4},
    )


def test_compose_video_result_marks_partial_failures_without_hiding_success(
    tmp_path: Path,
) -> None:
    first = _frame(tmp_path / "video" / "frames" / "frame-1.jpg", 0, 0.0)
    second = _frame(tmp_path / "video" / "frames" / "frame-2.jpg", 10, 5.0)
    frame_error = ProviderError(
        "Frame provider failed.",
        code="PROVIDER_UNAVAILABLE",
        details={
            "video_frame_indices": (10,),
            "video_frame_timestamps_seconds": (5.0,),
            "provider_calls_attempted": 1,
            "settled_model_usage": (
                {
                    "model": "vision-model",
                    "input_count": 3,
                    "output_count": 1,
                    "unit": "tokens",
                },
            ),
        },
    )
    audio_error = ProviderError(
        "Audio provider failed.",
        code="PROVIDER_RESPONSE_INVALID",
        details={
            "provider_calls_attempted": 1,
            "settled_model_usage": (
                {
                    "model": "audio-model",
                    "input_count": 4,
                    "output_count": 2,
                    "unit": "tokens",
                },
            ),
        },
    )
    audio = tmp_path / "video" / "audio.mp3"
    audio.write_bytes(b"mp3-placeholder")
    outcome = VideoRecognitionOutcome(
        output_root=tmp_path / "video",
        retained_frames=(first, second),
        frame_outcomes=(
            BatchItemOutcome(
                index=0,
                result=_frame_result(
                    markdown="First board.",
                    indices=(0,),
                    timestamps=(0.0,),
                ),
            ),
            BatchItemOutcome(index=1, error=frame_error),
        ),
        audio_artifact=audio,
        audio_error=audio_error,
    )

    result = compose_video_result(outcome)

    assert result.status == "partial"
    assert "First board." in result.markdown
    assert "Recognition error: `PROVIDER_UNAVAILABLE`" in result.markdown
    assert "Recognition error: `PROVIDER_RESPONSE_INVALID`" in result.markdown
    assert result.metadata["successful_video_frame_group_count"] == 1
    assert result.metadata["failed_video_frame_group_count"] == 1
    assert result.metadata["audio_state"] == "failed"
    assert result.metadata["current_run_provider_call_count"] == 3
    assert result.metadata["current_model_token_usage"] == (
        {"model": "vision-model", "input_tokens": 13, "output_tokens": 3},
        {"model": "audio-model", "input_tokens": 4, "output_tokens": 2},
    )


def test_compose_video_result_describes_silent_video_without_fake_transcript(
    tmp_path: Path,
) -> None:
    frame = _frame(tmp_path / "video" / "frames" / "frame-1.jpg", 0, 0.0)
    outcome = VideoRecognitionOutcome(
        output_root=tmp_path / "video",
        retained_frames=(frame,),
        frame_outcomes=(
            BatchItemOutcome(
                index=0,
                result=_frame_result(
                    markdown="Board only.",
                    indices=(0,),
                    timestamps=(0.0,),
                ),
            ),
        ),
        audio_error=VideoError("No stream.", code="VIDEO_NO_AUDIO_STREAM"),
    )

    result = compose_video_result(outcome)

    assert result.status == "complete"
    assert result.metadata["audio_state"] == "absent"
    assert result.markdown.endswith(
        "# Video audio\n\nNo audio stream was present.\n"
    )


def test_compose_video_result_keeps_whole_frame_branch_failure(
    tmp_path: Path,
) -> None:
    frame = _frame(tmp_path / "video" / "frames" / "frame-1.jpg", 0, 0.0)
    audio = tmp_path / "video" / "audio.mp3"
    audio.write_bytes(b"mp3-placeholder")
    outcome = VideoRecognitionOutcome(
        output_root=tmp_path / "video",
        retained_frames=(frame,),
        frame_error=ProviderError(
            "Frame branch failed.",
            code="PROVIDER_UNAVAILABLE",
            details={"provider_calls_attempted": 1},
        ),
        audio_artifact=audio,
        audio_result=_audio_result(),
    )

    result = compose_video_result(outcome)

    assert result.status == "partial"
    assert "## Frame recognition branch" in result.markdown
    assert "Recognition error: `PROVIDER_UNAVAILABLE`" in result.markdown
    assert "Audio transcript." in result.markdown
    assert result.metadata["video_frame_group_count"] == 0
    assert result.metadata["video_frame_error_code"] == "PROVIDER_UNAVAILABLE"
    assert result.metadata["current_run_provider_call_count"] == 2


def test_compose_video_result_rejects_fully_failed_outcome(tmp_path: Path) -> None:
    frame = _frame(tmp_path / "video" / "frames" / "frame-1.jpg", 0, 0.0)
    outcome = VideoRecognitionOutcome(
        output_root=tmp_path / "video",
        retained_frames=(frame,),
        frame_outcomes=(
            BatchItemOutcome(
                index=0,
                error=ProviderError("Frame provider failed."),
            ),
        ),
        audio_error=ProviderError("Audio provider failed."),
    )

    with pytest.raises(ValueError, match="failed video outcome"):
        compose_video_result(outcome)


def test_compose_video_result_rejects_missing_retained_artifact(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "video"
    missing = RetainedVideoFrame(
        0,
        0.0,
        output_root / "frames" / "missing.jpg",
    )
    outcome = VideoRecognitionOutcome(
        output_root=output_root,
        retained_frames=(missing,),
        frame_outcomes=(
            BatchItemOutcome(
                index=0,
                result=_frame_result(
                    markdown="Board content.",
                    indices=(0,),
                    timestamps=(0.0,),
                ),
            ),
        ),
        audio_error=ProviderError("Audio provider failed."),
    )

    with pytest.raises(OutputError, match="artifact"):
        compose_video_result(outcome)


def test_compose_video_result_rejects_frame_identity_drift(tmp_path: Path) -> None:
    frame = _frame(tmp_path / "video" / "frames" / "frame-1.jpg", 0, 0.0)
    outcome = VideoRecognitionOutcome(
        output_root=tmp_path / "video",
        retained_frames=(frame,),
        frame_outcomes=(
            BatchItemOutcome(
                index=0,
                result=_frame_result(
                    markdown="Wrong identity.",
                    indices=(10,),
                    timestamps=(5.0,),
                ),
            ),
        ),
        audio_error=ProviderError("Audio provider failed."),
    )

    with pytest.raises(ValueError, match="does not match retained frames"):
        compose_video_result(outcome)


def test_compose_video_result_rejects_out_of_order_group_indices(
    tmp_path: Path,
) -> None:
    first = _frame(tmp_path / "video" / "frames" / "frame-1.jpg", 0, 0.0)
    second = _frame(tmp_path / "video" / "frames" / "frame-2.jpg", 10, 5.0)
    outcome = VideoRecognitionOutcome(
        output_root=tmp_path / "video",
        retained_frames=(first, second),
        frame_outcomes=(
            BatchItemOutcome(
                index=1,
                result=_frame_result(
                    markdown="First board.",
                    indices=(0,),
                    timestamps=(0.0,),
                ),
            ),
            BatchItemOutcome(
                index=0,
                result=_frame_result(
                    markdown="Second board.",
                    indices=(10,),
                    timestamps=(5.0,),
                ),
            ),
        ),
        audio_error=VideoError("No stream.", code="VIDEO_NO_AUDIO_STREAM"),
    )

    with pytest.raises(ValueError, match="contiguous caller ordering"):
        compose_video_result(outcome)
