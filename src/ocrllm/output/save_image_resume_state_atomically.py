"""Atomically save one completed image result before final publication."""

from __future__ import annotations

import atexit
import os
from pathlib import Path
from uuid import uuid4

from ..errors import OutputError
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
        with temporary_path.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
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


def _delete_temporary_path_at_exit(temporary_path: Path) -> None:
    try:
        temporary_path.unlink(missing_ok=True)
    except (OSError, ValueError):
        pass
