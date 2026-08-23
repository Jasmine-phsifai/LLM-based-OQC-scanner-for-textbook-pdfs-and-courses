"""Verify a final Markdown artifact against completed image resume state."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..errors import OCRLLMError, ResumeStateError
from ..image_resume_state import ImageResumeState


_CHUNK_BYTES = 1024 * 1024


def validate_image_resume_output(
    output_path: Path,
    state: ImageResumeState,
) -> None:
    """Fail closed when the durable final artifact was edited or replaced."""
    try:
        expected_byte_size = len(state.markdown.encode("utf-8"))
        digest = hashlib.sha256()
        stream = output_path.open("rb")
        primary_error: BaseException | None = None
        try:
            try:
                bytes_read = 0
                while bytes_read <= expected_byte_size:
                    read_size = min(
                        _CHUNK_BYTES,
                        expected_byte_size - bytes_read + 1,
                    )
                    chunk = stream.read(read_size)
                    if not chunk:
                        break
                    bytes_read += len(chunk)
                    if bytes_read > expected_byte_size:
                        raise ResumeStateError(
                            "The final image output does not match "
                            "the resume state.",
                            code="RESUME_STATE_MISMATCH",
                        ) from None
                    digest.update(chunk)
            except (OSError, ValueError, MemoryError):
                raise ResumeStateError(
                    "The final image output could not be validated for resume.",
                    code="RESUME_STATE_MISMATCH",
                ) from None
            if bytes_read != expected_byte_size:
                raise ResumeStateError(
                    "The final image output does not match the resume state.",
                    code="RESUME_STATE_MISMATCH",
                ) from None
        except BaseException as error:
            primary_error = error
            raise
        finally:
            _close_resume_output_stream(stream, primary_error=primary_error)
    except ResumeStateError:
        raise
    except (OSError, ValueError, MemoryError):
        raise ResumeStateError(
            "The final image output could not be validated for resume.",
            code="RESUME_STATE_MISMATCH",
        ) from None
    if digest.hexdigest() != state.final_markdown_sha256:
        raise ResumeStateError(
            "The final image output does not match the resume state.",
            code="RESUME_STATE_MISMATCH",
        ) from None


def _close_resume_output_stream(
    stream,
    *,
    primary_error: BaseException | None,
) -> None:
    """Close the final-output stream without replacing an active failure."""

    try:
        stream.close()
    except (OSError, ValueError):
        if primary_error is None:
            raise ResumeStateError(
                "The final image output stream could not be closed safely.",
                code="RESUME_STATE_MISMATCH",
            ) from None
        if isinstance(primary_error, OCRLLMError):
            primary_error._add_safe_detail(
                "resume_output_stream_cleanup_failed",
                True,
            )
