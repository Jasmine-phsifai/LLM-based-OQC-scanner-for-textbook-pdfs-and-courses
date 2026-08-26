"""Atomically persist one video resume journal."""

from __future__ import annotations

import atexit
import os
from pathlib import Path
from uuid import uuid4

from .errors import OCRLLMError, OutputError
from .serialize_video_job_state import serialize_video_job_state
from .video_job_state import VideoJobState
from .video_job_state_file_limit import VIDEO_JOB_STATE_MAX_BYTES


def save_video_job_state_atomically(state_path: Path, state: VideoJobState) -> None:
    """Durably replace the one video journal through a sibling temporary file."""
    temporary_path = state_path.with_name(f".ocrllm-{uuid4().hex}.tmp")
    primary_error: BaseException | None = None
    try:
        raw = serialize_video_job_state(state)
        if len(raw) > VIDEO_JOB_STATE_MAX_BYTES:
            raise OutputError(
                "The video resume journal exceeds the safety limit.",
                code="OUTPUT_WRITE_FAILED",
            ) from None
        stream = temporary_path.open("xb")
        stream_primary: BaseException | None = None
        try:
            try:
                written = stream.write(raw)
                if written != len(raw):
                    raise OutputError(
                        "The video resume journal was not written completely.",
                        code="OUTPUT_WRITE_FAILED",
                    ) from None
                stream.flush()
                os.fsync(stream.fileno())
            except (OSError, TypeError, ValueError):
                raise OutputError(
                    "The video resume journal could not be written atomically.",
                    code="OUTPUT_WRITE_FAILED",
                ) from None
        except BaseException as error:
            stream_primary = error
            raise
        finally:
            _close_stream(stream, primary_error=stream_primary)
        os.replace(temporary_path, state_path)
    except BaseException as error:
        primary_error = error
        if isinstance(error, OutputError):
            raise
        if isinstance(error, (OSError, TypeError, ValueError)):
            raise OutputError(
                "The video resume journal could not be written atomically.",
                code="OUTPUT_WRITE_FAILED",
            ) from None
        raise
    finally:
        try:
            temporary_path.unlink(missing_ok=True)
        except (OSError, ValueError):
            atexit.register(_delete_at_exit, temporary_path)
            if isinstance(primary_error, OCRLLMError):
                primary_error._add_safe_detail("state_file_cleanup_failed", True)


def _close_stream(stream, *, primary_error: BaseException | None) -> None:
    try:
        stream.close()
    except (OSError, TypeError, ValueError):
        if primary_error is None:
            raise OutputError(
                "The temporary video resume journal could not be closed safely.",
                code="OUTPUT_WRITE_FAILED",
            ) from None
        if isinstance(primary_error, OCRLLMError):
            primary_error._add_safe_detail("state_stream_cleanup_failed", True)


def _delete_at_exit(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except (OSError, ValueError):
        pass
