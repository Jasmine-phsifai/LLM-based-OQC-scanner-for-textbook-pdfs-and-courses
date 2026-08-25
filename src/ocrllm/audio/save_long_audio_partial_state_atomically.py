"""Atomically save one validated long-audio partial state."""

from __future__ import annotations

import atexit
import os
from pathlib import Path
from uuid import uuid4

from ..errors import OCRLLMError, OutputError
from .long_audio_partial_state import LongAudioPartialState
from .long_audio_partial_state_file_limit import (
    LONG_AUDIO_PARTIAL_STATE_MAX_BYTES,
)
from .serialize_long_audio_partial_state import serialize_long_audio_partial_state


_MAX_STATE_BYTES = LONG_AUDIO_PARTIAL_STATE_MAX_BYTES


def save_long_audio_partial_state_atomically(
    state_path: Path,
    state: LongAudioPartialState,
) -> None:
    """Durably replace an explicit path through one unique sibling file."""
    primary_error: BaseException | None = None
    temporary_path: Path | None = None
    try:
        if not isinstance(state_path, Path):
            raise TypeError
        raw = serialize_long_audio_partial_state(state)
        if len(raw) > _MAX_STATE_BYTES:
            raise OutputError(
                "The long-audio partial state exceeds the safety limit.",
                code="OUTPUT_WRITE_FAILED",
            ) from None
        temporary_path = state_path.with_name(f".ocrllm-{uuid4().hex}.tmp")
        stream = temporary_path.open("xb")
        stream_primary: BaseException | None = None
        try:
            try:
                written_bytes = stream.write(raw)
                if written_bytes != len(raw):
                    raise OutputError(
                        "The long-audio partial state was not written completely.",
                        code="OUTPUT_WRITE_FAILED",
                    ) from None
                stream.flush()
                os.fsync(stream.fileno())
            except (OSError, TypeError, ValueError):
                raise OutputError(
                    "The long-audio partial state could not be written atomically.",
                    code="OUTPUT_WRITE_FAILED",
                ) from None
        except BaseException as error:
            stream_primary = error
            raise
        finally:
            _close_state_stream(stream, primary_error=stream_primary)
        os.replace(temporary_path, state_path)
    except OutputError as error:
        primary_error = error
        raise
    except (OSError, TypeError, ValueError):
        output_error = OutputError(
            "The long-audio partial state could not be written atomically.",
            code="OUTPUT_WRITE_FAILED",
        )
        primary_error = output_error
        raise output_error from None
    except BaseException as error:
        primary_error = error
        raise
    finally:
        if temporary_path is not None:
            _clean_temporary_path(temporary_path, primary_error=primary_error)


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
            raise OutputError(
                "The temporary long-audio partial state could not be closed safely.",
                code="OUTPUT_WRITE_FAILED",
            ) from None
        raise


def _clean_temporary_path(
    temporary_path: Path,
    *,
    primary_error: BaseException | None,
) -> None:
    try:
        temporary_path.unlink(missing_ok=True)
    except BaseException as cleanup_error:
        if isinstance(cleanup_error, (OSError, TypeError, ValueError)):
            atexit.register(_delete_temporary_path_at_exit, temporary_path)
            if isinstance(primary_error, OCRLLMError):
                primary_error._add_safe_detail("state_file_cleanup_failed", True)
            return
        if primary_error is not None:
            if isinstance(primary_error, OCRLLMError):
                primary_error._add_safe_detail("state_file_cleanup_failed", True)
            return
        raise


def _delete_temporary_path_at_exit(temporary_path: Path) -> None:
    try:
        temporary_path.unlink(missing_ok=True)
    except (OSError, TypeError, ValueError):
        pass
