"""Validate every persisted video-job input before resumed dispatch."""

from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path

from .build_owned_media_fingerprint import build_owned_media_fingerprint
from .config import Config
from .errors import InvalidSource, ResumeStateError, UnsupportedFormat
from .hash_video_snapshot import hash_video_snapshot
from .plan_video_frame_groups import plan_video_frame_groups
from .prepare_video_job_audio_state import prepare_video_job_audio_state
from .restore_video_job_frames import restore_video_job_frames
from .retained_video_frame import RetainedVideoFrame
from .reuse_image_resume_state import reuse_image_resume_state
from .validate_image_resume_identity import validate_image_resume_identity
from .video_job_state import VideoJobState


def validate_video_job_finalization_state(
    state: VideoJobState,
    *,
    result_path: Path,
) -> None:
    """Reject an impossible final-result/journal combination before dispatch."""
    try:
        result_exists = os.path.lexists(result_path)
        if result_exists and not result_path.is_file():
            raise ResumeStateError(
                "The fixed video result path is not a regular file.",
                code="RESUME_STATE_INVALID",
            ) from None
    except ResumeStateError:
        raise
    except (OSError, ValueError):
        raise ResumeStateError(
            "The fixed video result path could not be inspected safely.",
            code="RESUME_STATE_INVALID",
        ) from None
    if result_exists and state.final_markdown_sha256 is None:
        raise ResumeStateError(
            "An existing video result has no journaled final identity.",
            code="RESUME_STATE_MISMATCH",
        ) from None


def validate_video_job_resume(
    state: VideoJobState,
    *,
    source_path: Path,
    snapshot_path: Path,
    output_root: Path,
    image_config: Config,
    audio_config: Config,
    audio_interval_minutes: int | None,
) -> tuple[RetainedVideoFrame, ...]:
    """Return verified frames only after source, plan, and audio all match."""
    byte_size, sha256 = hash_video_snapshot(snapshot_path)
    current_source = build_owned_media_fingerprint(
        source_path,
        byte_size=byte_size,
        sha256=sha256,
    )
    if current_source != state.source:
        raise _mismatch("The video source no longer matches the journal.")
    if (
        state.audio.model != audio_config.audio_model.name
        or state.audio.interval_minutes != audio_interval_minutes
    ):
        raise _mismatch("The video audio request no longer matches the journal.")

    frames = restore_video_job_frames(state, output_root=output_root)
    current_groups = plan_video_frame_groups(frames, config=image_config)
    saved_plan = tuple(
        replace(group, image_state=None) for group in state.frame_groups
    )
    if current_groups != saved_plan:
        raise _mismatch("The retained video frame plan no longer matches the journal.")
    for saved_group, current_group in zip(
        state.frame_groups,
        current_groups,
        strict=True,
    ):
        if saved_group.image_state is None:
            continue
        validate_image_resume_identity(saved_group.image_state, current_group.identity)
        if saved_group.image_state.markdown:
            reuse_image_resume_state(saved_group.image_state, current_group.identity)

    if state.audio.state == "ready":
        try:
            current_audio = prepare_video_job_audio_state(
                output_root / "audio.mp3",
                config=audio_config,
                interval_minutes=audio_interval_minutes,
            )
        except (InvalidSource, UnsupportedFormat):
            raise _mismatch(
                "The extracted video audio is missing, changed, or unreadable."
            ) from None
        saved_audio = replace(
            state.audio,
            short_state=None,
            long_state=None,
        )
        if current_audio != saved_audio:
            raise _mismatch("The extracted video audio no longer matches the journal.")
        _validate_saved_long_audio_plan(state)
    return frames


def _validate_saved_long_audio_plan(state: VideoJobState) -> None:
    saved = state.audio.long_state
    if saved is None:
        return
    from .audio.build_long_audio_interval_windows import (
        build_long_audio_interval_windows,
    )
    from .audio.fingerprint_long_audio_request import fingerprint_long_audio_request
    from .audio.reuse_long_audio_partial_state import reuse_long_audio_partial_state

    assert state.audio.artifact is not None
    if state.audio.mode == "whole":
        plan = (
            fingerprint_long_audio_request(
                source_sha256=state.audio.artifact.sha256,
                mode="whole",
                provider="google",
                model=state.audio.model,
                transport="google_files",
            ),
        )
    else:
        assert state.audio.mode == "interval"
        assert state.audio.interval_minutes is not None
        assert state.audio.duration_seconds is not None
        windows = build_long_audio_interval_windows(
            duration_seconds=state.audio.duration_seconds,
            interval_minutes=state.audio.interval_minutes,
        )
        plan = tuple(
            fingerprint_long_audio_request(
                source_sha256=state.audio.artifact.sha256,
                mode="interval",
                provider="google",
                model=state.audio.model,
                transport="google_files",
                window=window,
            )
            for window in windows
        )
    reuse_long_audio_partial_state(saved, plan)


def _mismatch(message: str) -> ResumeStateError:
    return ResumeStateError(message, code="RESUME_STATE_MISMATCH")
