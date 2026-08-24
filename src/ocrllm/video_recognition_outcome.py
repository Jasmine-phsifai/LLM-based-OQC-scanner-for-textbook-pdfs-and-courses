"""Settled image and audio branches from one video recognition call."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Literal

from .batch_item_outcome import BatchItemOutcome
from .errors import OCRLLMError, VideoError
from .result import RecognitionResult
from .retained_video_frame import RetainedVideoFrame


@dataclass(frozen=True, slots=True, kw_only=True)
class VideoRecognitionOutcome:
    """Expose video branch results without inventing a combined document."""

    output_root: Path
    retained_frames: tuple[RetainedVideoFrame, ...]
    frame_outcomes: tuple[BatchItemOutcome, ...] = ()
    frame_error: OCRLLMError | None = None
    audio_artifact: Path | None = None
    audio_result: RecognitionResult | None = None
    audio_error: OCRLLMError | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.output_root, Path):
            raise TypeError("video output_root must be a pathlib.Path") from None
        if type(self.retained_frames) is not tuple or not self.retained_frames:
            raise ValueError("video retained_frames must be a nonempty exact tuple")
        if any(type(frame) is not RetainedVideoFrame for frame in self.retained_frames):
            raise TypeError(
                "video retained_frames must contain exact RetainedVideoFrame values"
            ) from None
        if any(
            current.frame_index <= previous.frame_index
            or current.timestamp_seconds < previous.timestamp_seconds
            for previous, current in pairwise(self.retained_frames)
        ):
            raise ValueError(
                "video retained_frames must remain in source order"
            ) from None
        frames_directory = self.output_root / "frames"
        if any(
            frame.path.parent != frames_directory
            for frame in self.retained_frames
        ):
            raise ValueError(
                "video retained frame paths must use the exact output_root/frames layout"
            ) from None
        if type(self.frame_outcomes) is not tuple:
            raise TypeError("video frame_outcomes must be an exact tuple") from None
        if any(type(outcome) is not BatchItemOutcome for outcome in self.frame_outcomes):
            raise TypeError(
                "video frame_outcomes must contain exact BatchItemOutcome values"
            ) from None
        for frame_outcome in self.frame_outcomes:
            if frame_outcome.result is None:
                continue
            if type(frame_outcome.result) is not RecognitionResult:
                raise TypeError(
                    "video frame results must be exact RecognitionResult values"
                ) from None
            if frame_outcome.result.source_type != "image":
                raise ValueError("video frame results must describe images") from None
        if (not self.frame_outcomes) == (self.frame_error is None):
            raise ValueError(
                "video outcome must carry frame outcomes or one frame error"
            ) from None
        if self.frame_error is not None and not isinstance(
            self.frame_error,
            OCRLLMError,
        ):
            raise TypeError("video frame_error must be an OCRLLMError") from None
        if (self.audio_result is None) == (self.audio_error is None):
            raise ValueError(
                "video outcome must carry exactly one audio result or error"
            ) from None
        if self.audio_result is not None:
            if type(self.audio_result) is not RecognitionResult:
                raise TypeError(
                    "video audio_result must be an exact RecognitionResult"
                ) from None
            if self.audio_result.source_type != "audio":
                raise ValueError("video audio_result must describe audio") from None
            if self.audio_artifact is None:
                raise ValueError(
                    "recognized video audio requires its retained artifact"
                ) from None
        if self.audio_error is not None and not isinstance(
            self.audio_error,
            OCRLLMError,
        ):
            raise TypeError("video audio_error must be an OCRLLMError") from None
        if (
            self.audio_error is not None
            and self.audio_error.code == "VIDEO_NO_AUDIO_STREAM"
            and not isinstance(self.audio_error, VideoError)
        ):
            raise TypeError(
                "VIDEO_NO_AUDIO_STREAM must use a VideoError"
            ) from None
        if self.audio_artifact is not None and not isinstance(
            self.audio_artifact,
            Path,
        ):
            raise TypeError("video audio_artifact must be a pathlib.Path") from None
        if (
            self.audio_artifact is not None
            and self.audio_error is not None
            and self.audio_error.code == "VIDEO_NO_AUDIO_STREAM"
        ):
            raise ValueError(
                "an absent audio stream cannot have an artifact"
            ) from None
        if (
            self.audio_artifact is not None
            and self.audio_artifact != self.output_root / "audio.mp3"
        ):
            raise ValueError(
                "video audio artifact must use the exact output_root/audio.mp3 path"
            ) from None

    @property
    def audio_state(self) -> Literal["recognized", "absent", "failed"]:
        """Describe the settled audio branch without hiding its typed error."""
        if self.audio_result is not None:
            return "recognized"
        assert self.audio_error is not None
        if self.audio_error.code == "VIDEO_NO_AUDIO_STREAM":
            return "absent"
        return "failed"

    @property
    def status(self) -> Literal["complete", "partial", "failed"]:
        """Summarize usability while preserving every branch-level fact."""
        successful_frames = sum(
            outcome.succeeded for outcome in self.frame_outcomes
        )
        all_frames_complete = bool(self.frame_outcomes) and all(
            outcome.result is not None and outcome.result.status == "complete"
            for outcome in self.frame_outcomes
        )
        audio_is_complete = self.audio_state == "absent" or (
            self.audio_result is not None
            and self.audio_result.status == "complete"
        )
        if all_frames_complete and audio_is_complete:
            return "complete"
        if successful_frames or self.audio_result is not None:
            return "partial"
        return "failed"
