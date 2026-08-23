"""Atomically save one completed image result before final publication."""

from __future__ import annotations

import atexit
import os
from pathlib import Path
from uuid import uuid4

from ..errors import OCRLLMError, OutputError
from ..image_resume_state import ImageResumeState
from ..serialize_image_resume_state import serialize_image_resume_state


_MAX_STATE_BYTES = 16 * 1024 * 1024


def save_image_resume_state_atomically(
    state_path: Path,
    state: ImageResumeState,
) -> None:
    """Durably replace state through a unique sibling temporary file."""
    temporary_path = state_path.with_name(f".ocrllm-{uuid4().hex}.tmp")
    try:
        raw = serialize_image_resume_state(state)
        if len(raw) > _MAX_STATE_BYTES:
            raise OutputError(
                "The completed image result exceeds the resume-state limit.",
                code="OUTPUT_WRITE_FAILED",
            ) from None
        stream = temporary_path.open("xb")
        primary_error: BaseException | None = None
        try:
            try:
                written_bytes = stream.write(raw)
                if written_bytes != len(raw):
                    raise OutputError(
                        "The image resume state was not written completely.",
                        code="OUTPUT_WRITE_FAILED",
                    ) from None
                stream.flush()
                os.fsync(stream.fileno())
            except (OSError, TypeError, ValueError):
                raise OutputError(
                    "The image resume state could not be written atomically.",
                    code="OUTPUT_WRITE_FAILED",
                ) from None
        except BaseException as error:
            primary_error = error
            raise
        finally:
            _close_state_stream(stream, primary_error=primary_error)
        os.replace(temporary_path, state_path)
    except OutputError:
        raise
    except (OSError, TypeError, ValueError):
        raise OutputError(
            "The image resume state could not be written atomically.",
            code="OUTPUT_WRITE_FAILED",
        ) from None
    finally:
        try:
            temporary_path.unlink(missing_ok=True)
        except (OSError, ValueError):
            atexit.register(_delete_temporary_path_at_exit, temporary_path)


def _close_state_stream(
    stream,
    *,
    primary_error: BaseException | None,
) -> None:
    """Close the state stream without replacing an active failure."""

    try:
        stream.close()
    except (OSError, TypeError, ValueError):
        if primary_error is None:
            raise OutputError(
                "The temporary image resume state could not be closed safely.",
                code="OUTPUT_WRITE_FAILED",
            ) from None
        if isinstance(primary_error, OCRLLMError):
            primary_error._add_safe_detail("state_stream_cleanup_failed", True)


def _delete_temporary_path_at_exit(temporary_path: Path) -> None:
    try:
        temporary_path.unlink(missing_ok=True)
    except (OSError, ValueError):
        pass
