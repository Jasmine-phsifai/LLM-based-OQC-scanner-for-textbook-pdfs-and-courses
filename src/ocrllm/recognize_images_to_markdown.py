"""Recognize pre-batched images into one resumable Markdown file."""

from __future__ import annotations

from pathlib import Path

from .providers.provider_model import ProviderModel
from .result import RecognitionResult


def recognize_images_to_markdown(
    batches: tuple[tuple[str | Path, ...], ...],
    *,
    provider: (
        ProviderModel
        | list[ProviderModel]
        | list[list[ProviderModel]]
    ),
    image_task: str,
    output_path: str | Path | None = None,
    timeout_seconds: float = 120.0,
    overwrite: bool = False,
) -> RecognitionResult:
    """Settle caller-planned batches through fixed provider lanes."""
    from .build_merged_image_resume_state import build_merged_image_resume_state
    from .clear_public_error import clear_public_error
    from .config import Config
    from .errors import OCRLLMError
    from .execute_merged_image_plan import execute_merged_image_plan
    from .finalize_merged_image_result import finalize_merged_image_result
    from .fingerprint_merged_image_batches import fingerprint_merged_image_batches
    from .normalize_merged_image_batches import normalize_merged_image_batches
    from .normalize_provider_model_lanes import normalize_provider_model_lanes
    from .output.output_target_claims import OutputTargetClaims
    from .output.preflight_resumable_markdown_output import (
        preflight_resumable_markdown_output,
    )
    from .output.resolve_resume_state_path import resolve_resume_state_path
    from .output.resolve_merged_image_output_path import (
        resolve_merged_image_output_path,
    )
    from .output.save_merged_image_resume_state_atomically import (
        save_merged_image_resume_state_atomically,
    )
    from .resolve_merged_image_prompt import resolve_merged_image_prompt

    public_error: OCRLLMError | None = None
    try:
        provider_lanes = normalize_provider_model_lanes(
            provider,
            distinguish_runtime_settings=True,
        )
        normalized_batches = normalize_merged_image_batches(batches)
        prompt, prompt_version = resolve_merged_image_prompt(
            provider_lanes[0][0],
            image_task,
        )
        for candidate in (
            candidate for lane in provider_lanes for candidate in lane
        ):
            resolve_merged_image_prompt(candidate, image_task)
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
        state_path = resolve_resume_state_path(resolved_output_path)
        with OutputTargetClaims() as claims:
            claims.claim(resolved_output_path)
            preflight_resumable_markdown_output(
                resolved_output_path,
                state_path,
                resume=False,
                overwrite=overwrite,
            )
            save_merged_image_resume_state_atomically(state_path, state)
            (
                state,
                current_usage,
                reused_slot_count,
                provider_failures,
            ) = execute_merged_image_plan(
                state,
                normalized_batches,
                provider_lanes=provider_lanes,
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
                provider_failures=provider_failures,
                overwrite=overwrite,
            )
    except OCRLLMError as error:
        public_error = error
    clear_public_error(public_error)
    raise public_error from None
