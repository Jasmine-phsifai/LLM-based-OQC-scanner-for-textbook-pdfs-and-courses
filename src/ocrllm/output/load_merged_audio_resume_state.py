"""Load one bounded merged-audio resume sidecar."""

from __future__ import annotations

import os
from pathlib import Path

from ..errors import OCRLLMError, ResumeStateError
from ..merged_audio_resume_state import MergedAudioResumeState


MERGED_AUDIO_RESUME_STATE_MAX_BYTES = 16 * 1024 * 1024


def load_merged_audio_resume_state(state_path: Path) -> MergedAudioResumeState:
    """Return strict state or one redacted typed failure."""
    try:
        if not os.path.lexists(state_path) or not state_path.is_file():
            raise ResumeStateError(
                "The merged-audio resume state is missing or invalid.",
                code="RESUME_STATE_INVALID",
            ) from None
        if state_path.stat().st_size > MERGED_AUDIO_RESUME_STATE_MAX_BYTES:
            raise ResumeStateError(
                "The merged-audio resume state exceeds the safety limit.",
                code="RESUME_STATE_INVALID",
            ) from None
        stream = state_path.open("rb")
        primary_error: BaseException | None = None
        try:
            try:
                raw = stream.read(MERGED_AUDIO_RESUME_STATE_MAX_BYTES + 1)
            except (OSError, ValueError, MemoryError):
                raise ResumeStateError(
                    "The merged-audio resume state could not be read safely.",
                    code="RESUME_STATE_INVALID",
                ) from None
            if len(raw) > MERGED_AUDIO_RESUME_STATE_MAX_BYTES:
                raise ResumeStateError(
                    "The merged-audio resume state exceeds the safety limit.",
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
                        "The merged-audio resume state could not be closed safely.",
                        code="RESUME_STATE_INVALID",
                    ) from None
                if isinstance(primary_error, OCRLLMError):
                    primary_error._add_safe_detail(
                        "state_stream_cleanup_failed",
                        True,
                    )
    except ResumeStateError:
        raise
    except (OSError, ValueError):
        raise ResumeStateError(
            "The merged-audio resume state could not be read safely.",
            code="RESUME_STATE_INVALID",
        ) from None
    return MergedAudioResumeState.from_bytes(raw)
