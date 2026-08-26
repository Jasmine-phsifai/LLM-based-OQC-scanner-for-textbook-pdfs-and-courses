"""Load one bounded video resume journal."""

from __future__ import annotations

import os
from pathlib import Path

from .errors import OCRLLMError, ResumeStateError
from .parse_video_job_state import parse_video_job_state
from .video_job_state import VideoJobState
from .video_job_state_file_limit import VIDEO_JOB_STATE_MAX_BYTES


def load_video_job_state(state_path: Path) -> VideoJobState:
    """Return strict state or a redacted typed failure."""
    try:
        if not os.path.lexists(state_path) or not state_path.is_file():
            raise ResumeStateError(
                "The video resume journal is missing or is not a regular file.",
                code="RESUME_STATE_INVALID",
            ) from None
        if state_path.stat().st_size > VIDEO_JOB_STATE_MAX_BYTES:
            raise ResumeStateError(
                "The video resume journal exceeds the safety limit.",
                code="RESUME_STATE_INVALID",
            ) from None
        stream = state_path.open("rb")
        primary_error: BaseException | None = None
        try:
            try:
                raw = stream.read(VIDEO_JOB_STATE_MAX_BYTES + 1)
            except (OSError, ValueError, MemoryError):
                raise ResumeStateError(
                    "The video resume journal could not be read safely.",
                    code="RESUME_STATE_INVALID",
                ) from None
            if len(raw) > VIDEO_JOB_STATE_MAX_BYTES:
                raise ResumeStateError(
                    "The video resume journal exceeds the safety limit.",
                    code="RESUME_STATE_INVALID",
                ) from None
        except BaseException as error:
            primary_error = error
            raise
        finally:
            _close_stream(stream, primary_error=primary_error)
    except ResumeStateError:
        raise
    except (OSError, ValueError):
        raise ResumeStateError(
            "The video resume journal could not be read safely.",
            code="RESUME_STATE_INVALID",
        ) from None
    return parse_video_job_state(raw)


def _close_stream(stream, *, primary_error: BaseException | None) -> None:
    try:
        stream.close()
    except (OSError, ValueError):
        if primary_error is None:
            raise ResumeStateError(
                "The video resume journal stream could not be closed safely.",
                code="RESUME_STATE_INVALID",
            ) from None
        if isinstance(primary_error, OCRLLMError):
            primary_error._add_safe_detail("state_stream_cleanup_failed", True)
