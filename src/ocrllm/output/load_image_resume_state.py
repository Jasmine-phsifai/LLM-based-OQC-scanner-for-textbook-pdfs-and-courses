"""Load one optional bounded sibling image resume state file."""

from __future__ import annotations

import os
from pathlib import Path

from ..errors import OCRLLMError, ResumeStateError
from ..image_resume_state import ImageResumeState
from ..parse_image_resume_state import parse_image_resume_state


_MAX_STATE_BYTES = 16 * 1024 * 1024


def load_image_resume_state(state_path: Path) -> ImageResumeState | None:
    """Return strict state, None when absent, or a redacted typed failure."""
    try:
        if not os.path.lexists(state_path):
            return None
        if not state_path.is_file():
            raise ResumeStateError(
                "The image resume state path is not a regular file.",
                code="RESUME_STATE_INVALID",
            ) from None
        if state_path.stat().st_size > _MAX_STATE_BYTES:
            raise ResumeStateError(
                "The image resume state exceeds the safety limit.",
                code="RESUME_STATE_INVALID",
            ) from None
        stream = state_path.open("rb")
        primary_error: BaseException | None = None
        try:
            try:
                raw = stream.read(_MAX_STATE_BYTES + 1)
            except (OSError, ValueError, MemoryError):
                raise ResumeStateError(
                    "The image resume state could not be read safely.",
                    code="RESUME_STATE_INVALID",
                ) from None
            if len(raw) > _MAX_STATE_BYTES:
                raise ResumeStateError(
                    "The image resume state exceeds the safety limit.",
                    code="RESUME_STATE_INVALID",
                ) from None
        except BaseException as error:
            primary_error = error
            raise
        finally:
            _close_state_stream(stream, primary_error=primary_error)
    except ResumeStateError:
        raise
    except (OSError, ValueError):
        raise ResumeStateError(
            "The image resume state could not be read safely.",
            code="RESUME_STATE_INVALID",
        ) from None
    return parse_image_resume_state(raw)


def _close_state_stream(
    stream,
    *,
    primary_error: BaseException | None,
) -> None:
    """Close the state stream without replacing an active failure."""

    try:
        stream.close()
    except (OSError, ValueError):
        if primary_error is None:
            raise ResumeStateError(
                "The image resume state stream could not be closed safely.",
                code="RESUME_STATE_INVALID",
            ) from None
        if isinstance(primary_error, OCRLLMError):
            primary_error._add_safe_detail("state_stream_cleanup_failed", True)
