"""Restore original image batches through the owner-validated public boundary."""

from __future__ import annotations

from pathlib import Path


def restore_image_batch_plan(
    sources: tuple[str | Path, ...], *, output_path: str | Path
) -> tuple[tuple[Path, ...], ...]:
    """Return saved grouping after validating every current source identity.

    The result has exactly the same shape as ``batchify_images`` and can be
    passed directly to ``resume_images_to_markdown`` with changed providers or
    concurrency. No model is called and no output/state file is changed. The
    ordinary resume operation still validates the saved task and prompt version.
    Missing, malformed, or mismatched state is a typed failure, never permission
    to guess a new batch size or restart already settled work.
    """
    from .clear_public_error import clear_public_error
    from .errors import InvalidSource, OCRLLMError, ResumeStateError
    from .fingerprint_merged_image_batches import fingerprint_merged_image_batches
    from .output.load_merged_image_resume_state import load_merged_image_resume_state
    from .output.output_target_claims import OutputTargetClaims
    from .output.resolve_merged_image_output_path import resolve_merged_image_output_path
    from .output.resolve_resume_state_path import resolve_resume_state_path

    public_error: OCRLLMError | None = None
    try:
        if (type(sources) is not tuple or not sources
                or any(not isinstance(source, (str, Path)) for source in sources)):
            raise InvalidSource(
                "Image plan restoration requires an ordered nonempty tuple of sources.",
                code="SOURCE_INVALID", details={"provider_calls_attempted": 0},
            ) from None
        paths = tuple(Path(source) for source in sources)
        target = resolve_merged_image_output_path((paths,), output_path=output_path)
        with OutputTargetClaims() as claims:
            claims.claim(target)
            state = load_merged_image_resume_state(resolve_resume_state_path(target))
            if len(paths) != len(state.sources):
                raise ResumeStateError(
                    "The supplied images do not match the saved image plan.",
                    code="RESUME_STATE_MISMATCH",
                    details={"provider_calls_attempted": 0},
                ) from None
            batches = tuple(
                tuple(paths[index] for index in slot.source_indexes)
                for slot in state.slots
            )
            if fingerprint_merged_image_batches(batches) != state.sources:
                raise ResumeStateError(
                    "The supplied images do not match the saved image plan.",
                    code="RESUME_STATE_MISMATCH",
                    details={"provider_calls_attempted": 0},
                ) from None
            return batches
    except OCRLLMError as error:
        error._add_safe_detail("provider_calls_attempted", 0)
        public_error = error
    clear_public_error(public_error)
    raise public_error from None
