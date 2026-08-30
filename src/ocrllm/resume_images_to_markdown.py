"""Resume unresolved slots in one merged-image Markdown job."""

from __future__ import annotations

from pathlib import Path

from .providers.provider_model import ProviderModel
from .result import RecognitionResult


def resume_images_to_markdown(
    batches: tuple[tuple[str | Path, ...], ...],
    *,
    provider: ProviderModel,
    output_path: str | Path | None = None,
    timeout_seconds: float = 120.0,
) -> RecognitionResult:
    """Restore the saved task/plan and dispatch only unresolved batches."""
    from .build_merged_image_resume_state import build_merged_image_resume_state
    from .clear_public_error import clear_public_error
    from .config import Config
    from .errors import OCRLLMError
    from .execute_merged_image_plan import execute_merged_image_plan
    from .finalize_merged_image_result import finalize_merged_image_result
    from .fingerprint_merged_image_batches import fingerprint_merged_image_batches
    from .normalize_merged_image_batches import normalize_merged_image_batches
    from .output.load_merged_image_resume_state import load_merged_image_resume_state
    from .output.output_target_claims import OutputTargetClaims
    from .output.preflight_merged_image_output import preflight_merged_image_output
    from .output.resolve_image_resume_state_path import resolve_image_resume_state_path
    from .output.resolve_merged_image_output_path import (
        resolve_merged_image_output_path,
    )
    from .resolve_merged_image_prompt import resolve_merged_image_prompt

    public_error: OCRLLMError | None = None
    try:
        normalized_batches = normalize_merged_image_batches(batches)
        resolved_output_path = resolve_merged_image_output_path(
            normalized_batches,
            output_path=output_path,
        )
        state_path = resolve_image_resume_state_path(resolved_output_path)
        Config(timeout_seconds=timeout_seconds)
        with OutputTargetClaims() as claims:
            claims.claim(resolved_output_path)
            preflight_merged_image_output(
                resolved_output_path,
                state_path,
                resume=True,
                overwrite=False,
            )
            state = load_merged_image_resume_state(state_path)
            prompt, prompt_version = resolve_merged_image_prompt(
                provider,
                state.image_task,
            )
            sources = fingerprint_merged_image_batches(normalized_batches)
            requested_plan = build_merged_image_resume_state(
                normalized_batches,
                image_task=state.image_task,
                prompt_version=prompt_version,
                sources=sources,
            )
            _validate_resume_plan(state, requested_plan)
            historical_usage = state.usage
            state, current_usage, reused_slot_count = execute_merged_image_plan(
                state,
                normalized_batches,
                provider=provider,
                prompt=prompt,
                state_path=state_path,
                timeout_seconds=timeout_seconds,
            )
            return finalize_merged_image_result(
                state,
                output_path=resolved_output_path,
                state_path=state_path,
                current_usage=current_usage,
                historical_usage=historical_usage,
                reused_slot_count=reused_slot_count,
                overwrite=True,
            )
    except OCRLLMError as error:
        public_error = error
    clear_public_error(public_error)
    raise public_error from None


def _validate_resume_plan(state, requested_plan) -> None:
    from .errors import ResumeStateError

    if (
        state.image_task != requested_plan.image_task
        or state.prompt_version != requested_plan.prompt_version
        or state.sources != requested_plan.sources
        or tuple(slot.source_indexes for slot in state.slots)
        != tuple(slot.source_indexes for slot in requested_plan.slots)
    ):
        raise ResumeStateError(
            "The supplied image batches do not match the saved merged-image plan.",
            code="RESUME_STATE_MISMATCH",
            details={"provider_calls_attempted": 0},
        ) from None
