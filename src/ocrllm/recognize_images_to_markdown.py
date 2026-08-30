"""Recognize pre-batched images into one resumable Markdown file."""

from __future__ import annotations

from pathlib import Path

from .providers.provider_model import ProviderModel
from .result import RecognitionResult


def recognize_images_to_markdown(
    batches: tuple[tuple[str | Path, ...], ...],
    *,
    provider: ProviderModel,
    image_task: str,
    output_path: str | Path | None = None,
    timeout_seconds: float = 120.0,
    overwrite: bool = False,
) -> RecognitionResult:
    """Settle every caller-planned batch through one scalar provider."""
    from .build_merged_image_resume_state import build_merged_image_resume_state
    from .clear_public_error import clear_public_error
    from .config import Config
    from .errors import OCRLLMError
    from .execute_merged_image_plan import execute_merged_image_plan
    from .finalize_merged_image_result import finalize_merged_image_result
    from .fingerprint_merged_image_batches import fingerprint_merged_image_batches
    from .normalize_merged_image_batches import normalize_merged_image_batches
    from .output.output_target_claims import OutputTargetClaims
    from .output.preflight_merged_image_output import preflight_merged_image_output
    from .output.resolve_image_resume_state_path import resolve_image_resume_state_path
    from .output.resolve_merged_image_output_path import (
        resolve_merged_image_output_path,
    )
    from .output.save_merged_image_resume_state_atomically import (
        save_merged_image_resume_state_atomically,
    )
    from .resolve_merged_image_prompt import resolve_merged_image_prompt

    public_error: OCRLLMError | None = None
    try:
        normalized_batches = normalize_merged_image_batches(batches)
        prompt, prompt_version = resolve_merged_image_prompt(provider, image_task)
        Config(timeout_seconds=timeout_seconds, overwrite=overwrite)
        resolved_output_path = resolve_merged_image_output_path(
            normalized_batches,
            output_path=output_path,
        )
        sources = fingerprint_merged_image_batches(normalized_batches)
        state = build_merged_image_resume_state(
            normalized_batches,
            image_task=image_task,
            prompt_version=prompt_version,
            sources=sources,
        )
        state_path = resolve_image_resume_state_path(resolved_output_path)
        with OutputTargetClaims() as claims:
            claims.claim(resolved_output_path)
            preflight_merged_image_output(
                resolved_output_path,
                state_path,
                resume=False,
                overwrite=overwrite,
            )
            save_merged_image_resume_state_atomically(state_path, state)
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
                historical_usage=(),
                reused_slot_count=reused_slot_count,
                overwrite=overwrite,
            )
    except OCRLLMError as error:
        public_error = error
    clear_public_error(public_error)
    raise public_error from None
