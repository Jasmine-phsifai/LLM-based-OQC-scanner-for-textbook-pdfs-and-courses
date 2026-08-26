"""Restore and verify retained full frames from a video journal."""

from __future__ import annotations

from pathlib import Path

from .errors import ResumeStateError
from .hash_snapshot_bytes import hash_snapshot_bytes
from .retained_video_frame import RetainedVideoFrame
from .source_fingerprint_path import source_fingerprint_path
from .validate_source import MAX_SOURCE_BYTES
from .video_job_state import VideoJobState


def restore_video_job_frames(
    state: VideoJobState,
    *,
    output_root: Path,
) -> tuple[RetainedVideoFrame, ...]:
    """Validate every retained JPEG before any resumed provider dispatch."""
    frames = []
    expected_directory = output_root / "frames"
    for group in state.frame_groups:
        for frame_index, timestamp, source in zip(
            group.frame_indices,
            group.frame_timestamps_seconds,
            group.identity.sources,
            strict=True,
        ):
            path = source_fingerprint_path(source)
            if path.parent != expected_directory or path.suffix.casefold() != ".jpg":
                raise ResumeStateError(
                    "A retained video frame is outside the fixed job layout.",
                    code="RESUME_STATE_MISMATCH",
                ) from None
            try:
                byte_size, sha256 = hash_snapshot_bytes(
                    path,
                    maximum_byte_size=MAX_SOURCE_BYTES,
                )
            except Exception:
                raise ResumeStateError(
                    "A retained video frame is missing, changed, or unreadable.",
                    code="RESUME_STATE_MISMATCH",
                ) from None
            if byte_size != source.byte_size or sha256 != source.sha256:
                raise ResumeStateError(
                    "A retained video frame no longer matches the journal.",
                    code="RESUME_STATE_MISMATCH",
                ) from None
            frames.append(
                RetainedVideoFrame(
                    frame_index=frame_index,
                    timestamp_seconds=timestamp,
                    path=path,
                )
            )
    return tuple(frames)
