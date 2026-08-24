from __future__ import annotations

from pathlib import Path

import pytest

from ocrllm import (
    BatchItemOutcome,
    OCRLLMError,
    RecognitionResult,
    RetainedVideoFrame,
    VideoRecognitionOutcome,
)
from ocrllm.errors import VideoError


def _frame(path: Path) -> RetainedVideoFrame:
    return RetainedVideoFrame(
        frame_index=0,
        timestamp_seconds=0.0,
        path=path,
    )


def _frame_outcome() -> BatchItemOutcome:
    return BatchItemOutcome(
        index=0,
        result=RecognitionResult(
            markdown="Frame result.",
            source_type="image",
            metadata={
                "video_frame_indices": (0,),
                "video_frame_timestamps_seconds": (0.0,),
            },
        ),
    )


def test_video_outcome_rejects_frame_outside_declared_frames_directory(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "video"

    with pytest.raises(ValueError, match="exact output_root/frames layout"):
        VideoRecognitionOutcome(
            output_root=output_root,
            retained_frames=(_frame(tmp_path / "other" / "frame.jpg"),),
            frame_outcomes=(_frame_outcome(),),
            audio_error=VideoError(code="VIDEO_NO_AUDIO_STREAM"),
        )


def test_video_outcome_rejects_audio_outside_declared_output_root(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "video"

    with pytest.raises(ValueError, match="exact output_root/audio.mp3 path"):
        VideoRecognitionOutcome(
            output_root=output_root,
            retained_frames=(_frame(output_root / "frames" / "frame.jpg"),),
            frame_outcomes=(_frame_outcome(),),
            audio_artifact=tmp_path / "other" / "audio.mp3",
            audio_result=RecognitionResult(
                markdown="Audio result.",
                source_type="audio",
            ),
        )


def test_video_outcome_rejects_non_image_frame_result(tmp_path: Path) -> None:
    output_root = tmp_path / "video"
    wrong_result = RecognitionResult(
        markdown="Audio placed in a frame group.",
        source_type="audio",
    )

    with pytest.raises(ValueError, match="frame results must describe images"):
        VideoRecognitionOutcome(
            output_root=output_root,
            retained_frames=(
                _frame(output_root / "frames" / "frame.jpg"),
            ),
            frame_outcomes=(
                BatchItemOutcome(index=0, result=wrong_result),
            ),
            audio_error=VideoError(code="VIDEO_NO_AUDIO_STREAM"),
        )


def test_video_outcome_accepts_its_declared_owned_artifact_layout(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "video"
    audio_artifact = output_root / "audio.mp3"

    outcome = VideoRecognitionOutcome(
        output_root=output_root,
        retained_frames=(_frame(output_root / "frames" / "frame.jpg"),),
        frame_outcomes=(_frame_outcome(),),
        audio_artifact=audio_artifact,
        audio_result=RecognitionResult(
            markdown="Audio result.",
            source_type="audio",
        ),
    )

    assert outcome.audio_artifact == audio_artifact


def test_video_outcome_rejects_audio_artifact_for_absent_stream(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "video"

    with pytest.raises(
        ValueError,
        match="absent audio stream cannot have an artifact",
    ):
        VideoRecognitionOutcome(
            output_root=output_root,
            retained_frames=(
                _frame(output_root / "frames" / "frame.jpg"),
            ),
            frame_outcomes=(_frame_outcome(),),
            audio_artifact=output_root / "audio.mp3",
            audio_error=VideoError(code="VIDEO_NO_AUDIO_STREAM"),
        )


def test_video_outcome_requires_video_error_for_absent_stream(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "video"

    with pytest.raises(TypeError, match="VIDEO_NO_AUDIO_STREAM.*VideoError"):
        VideoRecognitionOutcome(
            output_root=output_root,
            retained_frames=(
                _frame(output_root / "frames" / "frame.jpg"),
            ),
            frame_outcomes=(_frame_outcome(),),
            audio_error=OCRLLMError(code="VIDEO_NO_AUDIO_STREAM"),
        )


def test_video_outcome_does_not_resolve_lexical_path_aliases(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "alias" / ".." / "video"

    with pytest.raises(ValueError, match="exact output_root/frames layout"):
        VideoRecognitionOutcome(
            output_root=output_root,
            retained_frames=(
                _frame(tmp_path / "video" / "frames" / "frame.jpg"),
            ),
            frame_outcomes=(_frame_outcome(),),
            audio_error=VideoError(code="VIDEO_NO_AUDIO_STREAM"),
        )


@pytest.mark.parametrize(
    ("indices", "timestamps"),
    [
        ((0, 0), (0.0, 1.0)),
        ((0, 10), (5.0, 0.0)),
    ],
)
def test_video_outcome_rejects_retained_frames_out_of_source_order(
    tmp_path: Path,
    indices: tuple[int, int],
    timestamps: tuple[float, float],
) -> None:
    output_root = tmp_path / "video"
    retained_frames = tuple(
        RetainedVideoFrame(
            frame_index,
            timestamp,
            output_root / "frames" / f"frame-{position}.jpg",
        )
        for position, (frame_index, timestamp) in enumerate(
            zip(indices, timestamps, strict=True)
        )
    )
    frame_result = RecognitionResult(
        markdown="Frames accepted in the supplied order.",
        source_type="image",
        metadata={
            "video_frame_indices": indices,
            "video_frame_timestamps_seconds": timestamps,
        },
    )

    with pytest.raises(ValueError, match="source order"):
        VideoRecognitionOutcome(
            output_root=output_root,
            retained_frames=retained_frames,
            frame_outcomes=(BatchItemOutcome(index=0, result=frame_result),),
            audio_error=VideoError(code="VIDEO_NO_AUDIO_STREAM"),
        )


def test_video_outcome_rejects_out_of_order_group_indices(tmp_path: Path) -> None:
    output_root = tmp_path / "video"
    retained_frames = (
        RetainedVideoFrame(0, 0.0, output_root / "frames" / "frame-0.jpg"),
        RetainedVideoFrame(10, 5.0, output_root / "frames" / "frame-10.jpg"),
    )
    frame_result = _frame_outcome().result
    assert frame_result is not None

    with pytest.raises(ValueError, match="contiguous caller ordering"):
        VideoRecognitionOutcome(
            output_root=output_root,
            retained_frames=retained_frames,
            frame_outcomes=(
                BatchItemOutcome(index=1, result=frame_result),
                BatchItemOutcome(index=0, result=frame_result),
            ),
            audio_error=VideoError(code="VIDEO_NO_AUDIO_STREAM"),
        )


@pytest.mark.parametrize(
    ("metadata", "message"),
    [
        ({}, "identity is missing or invalid"),
        (
            {
                "video_frame_indices": (10,),
                "video_frame_timestamps_seconds": (5.0,),
            },
            "does not match retained frames",
        ),
    ],
)
def test_video_outcome_rejects_missing_or_drifted_frame_group_identity(
    tmp_path: Path,
    metadata: dict[str, object],
    message: str,
) -> None:
    output_root = tmp_path / "video"
    frame_result = RecognitionResult(
        markdown="Frame result.",
        source_type="image",
        metadata=metadata,
    )

    with pytest.raises(ValueError, match=message):
        VideoRecognitionOutcome(
            output_root=output_root,
            retained_frames=(_frame(output_root / "frames" / "frame.jpg"),),
            frame_outcomes=(BatchItemOutcome(index=0, result=frame_result),),
            audio_error=VideoError(code="VIDEO_NO_AUDIO_STREAM"),
        )
