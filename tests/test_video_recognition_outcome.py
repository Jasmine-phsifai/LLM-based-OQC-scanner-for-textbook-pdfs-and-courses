from __future__ import annotations

from pathlib import Path

import pytest

from ocrllm import (
    BatchItemOutcome,
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
