"""Load one bounded merged-image resume sidecar."""

from __future__ import annotations

import os
from pathlib import Path

from ..errors import OCRLLMError, ResumeStateError
from ..merged_image_resume_state import MergedImageResumeState


MERGED_IMAGE_RESUME_STATE_MAX_BYTES = 16 * 1024 * 1024


def load_merged_image_resume_state(state_path: Path) -> MergedImageResumeState:
    """Return strict state or one redacted typed failure."""
    try:
        if not os.path.lexists(state_path):
            raise ResumeStateError(
                "The merged-image resume state does not exist.",
                code="RESUME_STATE_INVALID",
            ) from None
        if not state_path.is_file():
            raise ResumeStateError(
                "The merged-image resume state path is not a regular file.",
                code="RESUME_STATE_INVALID",
            ) from None
        if state_path.stat().st_size > MERGED_IMAGE_RESUME_STATE_MAX_BYTES:
            raise ResumeStateError(
                "The merged-image resume state exceeds the safety limit.",
                code="RESUME_STATE_INVALID",
            ) from None
        stream = state_path.open("rb")
        primary_error: BaseException | None = None
        try:
            try:
                raw = stream.read(MERGED_IMAGE_RESUME_STATE_MAX_BYTES + 1)
            except (OSError, ValueError, MemoryError):
                raise ResumeStateError(
                    "The merged-image resume state could not be read safely.",
                    code="RESUME_STATE_INVALID",
                ) from None
            if len(raw) > MERGED_IMAGE_RESUME_STATE_MAX_BYTES:
                raise ResumeStateError(
                    "The merged-image resume state exceeds the safety limit.",
                    code="RESUME_STATE_INVALID",
                ) from None
        except BaseException as error:
            primary_error = error
            raise
        finally:
            try:
                stream.close()
            except (OSError, ValueError):
                if primary_error is None:
                    raise ResumeStateError(
                        "The merged-image resume state could not be closed safely.",
                        code="RESUME_STATE_INVALID",
                    ) from None
                if isinstance(primary_error, OCRLLMError):
                    primary_error._add_safe_detail("state_stream_cleanup_failed", True)
    except ResumeStateError:
        raise
    except (OSError, ValueError):
        raise ResumeStateError(
            "The merged-image resume state could not be read safely.",
            code="RESUME_STATE_INVALID",
        ) from None
    return MergedImageResumeState.from_bytes(raw)
