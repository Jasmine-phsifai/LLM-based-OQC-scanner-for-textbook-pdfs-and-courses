"""Publish and clean up one fully settled video job."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

from .attach_current_video_evidence_to_error import (
    attach_current_video_evidence_to_error,
)
from .compose_video_result import compose_video_result
from .errors import OCRLLMError
from .publish_video_result import publish_video_result
from .result import RecognitionResult
from .video_job_journal import VideoJobJournal
from .video_recognition_outcome import VideoRecognitionOutcome


def finalize_video_job(
    outcome: VideoRecognitionOutcome,
    *,
    journal: VideoJobJournal,
    result_path: Path,
) -> RecognitionResult:
    """Publish once, verify crash coexistence, then remove the journal."""
    composed = compose_video_result(outcome)
    digest = hashlib.sha256(composed.markdown.encode("utf-8")).hexdigest()
    saved_digest = journal.state.final_markdown_sha256
    if saved_digest is not None and saved_digest != digest:
        from .errors import ResumeStateError

        raise ResumeStateError(
            "The settled video result no longer matches the journal.",
            code="RESUME_STATE_MISMATCH",
        ) from None

    if result_path.exists():
        if saved_digest is None:
            from .errors import ResumeStateError

            raise ResumeStateError(
                "An existing video result has no journaled final identity.",
                code="RESUME_STATE_MISMATCH",
            ) from None
        _validate_existing_result(result_path, expected=composed.markdown)
        result = replace(composed, output_path=result_path)
    else:
        try:
            journal.persist_final_digest(digest)
            result = publish_video_result(outcome, result_path)
        except OCRLLMError as error:
            attach_current_video_evidence_to_error(
                error,
                before=(composed,),
                primary_provider_calls_attempted=0,
            )
            raise

    try:
        journal.path.unlink()
    except (OSError, ValueError):
        metadata = dict(result.metadata)
        metadata["resume_state_removed"] = False
        return replace(
            result,
            status="partial",
            warnings=(
                *result.warnings,
                "The temporary video resume journal could not be removed.",
            ),
            metadata=metadata,
        )
    return result


def _validate_existing_result(path: Path, *, expected: str) -> None:
    from .errors import ResumeStateError

    expected_bytes = expected.encode("utf-8")
    try:
        with path.open("rb") as stream:
            raw = stream.read(len(expected_bytes) + 1)
    except (OSError, ValueError, MemoryError):
        raise ResumeStateError(
            "The existing video result could not be validated safely.",
            code="RESUME_STATE_INVALID",
        ) from None
    if raw != expected_bytes:
        raise ResumeStateError(
            "The existing video result no longer matches the journal.",
            code="RESUME_STATE_MISMATCH",
        ) from None
