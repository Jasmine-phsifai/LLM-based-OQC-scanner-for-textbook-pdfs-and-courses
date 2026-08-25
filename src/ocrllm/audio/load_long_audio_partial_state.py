"""Load one optional bounded long-audio partial-state file."""

from __future__ import annotations

import os
from pathlib import Path

from ..errors import OCRLLMError, ResumeStateError
from .long_audio_partial_state import LongAudioPartialState
from .long_audio_partial_state_file_limit import (
    LONG_AUDIO_PARTIAL_STATE_MAX_BYTES,
)
from .parse_long_audio_partial_state import parse_long_audio_partial_state


_MAX_STATE_BYTES = LONG_AUDIO_PARTIAL_STATE_MAX_BYTES


def load_long_audio_partial_state(
    state_path: Path,
) -> LongAudioPartialState | None:
    """Return strict state, None when absent, or one redacted typed failure."""
    try:
        if not isinstance(state_path, Path):
            raise TypeError
        if not os.path.lexists(state_path):
            return None
        if not state_path.is_file():
            raise ResumeStateError(
                "The long-audio partial state path is not a regular file.",
                code="RESUME_STATE_INVALID",
            ) from None
        if state_path.stat().st_size > _MAX_STATE_BYTES:
            raise ResumeStateError(
                "The long-audio partial state exceeds the safety limit.",
                code="RESUME_STATE_INVALID",
            ) from None
        stream = state_path.open("rb")
        primary_error: BaseException | None = None
        try:
            try:
                raw = stream.read(_MAX_STATE_BYTES + 1)
            except (OSError, TypeError, ValueError, MemoryError):
                raise ResumeStateError(
                    "The long-audio partial state could not be read safely.",
                    code="RESUME_STATE_INVALID",
                ) from None
            if len(raw) > _MAX_STATE_BYTES:
                raise ResumeStateError(
                    "The long-audio partial state exceeds the safety limit.",
                    code="RESUME_STATE_INVALID",
                ) from None
        except BaseException as error:
            primary_error = error
            raise
        finally:
            _close_state_stream(stream, primary_error=primary_error)
    except ResumeStateError:
        raise
    except (OSError, TypeError, ValueError):
        raise ResumeStateError(
            "The long-audio partial state could not be read safely.",
            code="RESUME_STATE_INVALID",
        ) from None
    return parse_long_audio_partial_state(raw)


def _close_state_stream(
    stream,
    *,
    primary_error: BaseException | None,
) -> None:
    try:
        stream.close()
    except BaseException as cleanup_error:
        if primary_error is not None:
            if isinstance(primary_error, OCRLLMError):
                primary_error._add_safe_detail("state_stream_cleanup_failed", True)
            return
        if isinstance(cleanup_error, (OSError, TypeError, ValueError)):
            raise ResumeStateError(
                "The long-audio partial state stream could not be closed safely.",
                code="RESUME_STATE_INVALID",
            ) from None
        raise

