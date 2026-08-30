"""Repair strict failed image slots without recreating resume state."""

from __future__ import annotations

from pathlib import Path

from .providers.provider_model import ProviderModel
from .result import RecognitionResult


_ProviderInput = (
    ProviderModel
    | list[ProviderModel]
    | list[list[ProviderModel]]
)


def repair_images_to_markdown(
    batches: tuple[tuple[str | Path, ...], ...],
    *,
    provider: _ProviderInput,
    image_task: str,
    output_path: str | Path | None = None,
    timeout_seconds: float = 120.0,
) -> RecognitionResult:
    """Replace current OCRLLM failed-slot markers using explicit current sources."""
    from .clear_public_error import clear_public_error
    from .config import Config
    from .errors import OCRLLMError
    from .normalize_merged_image_batches import normalize_merged_image_batches
    from .normalize_provider_model_lanes import normalize_provider_model_lanes
    from .output.claim_output_target import claim_output_target
    from .output.resolve_merged_image_output_path import (
        resolve_merged_image_output_path,
    )
    from .output.resolve_resume_state_path import resolve_resume_state_path
    from .parse_merged_image_failure_markers import (
        parse_merged_image_failure_markers,
    )
    from .read_repair_markdown import read_repair_markdown
    from .resolve_merged_image_prompt import resolve_merged_image_prompt
    from .repair_marked_image_batches import repair_marked_image_batches
    from .validate_image_group import validate_image_group

    public_error: OCRLLMError | None = None
    try:
        provider_lanes = normalize_provider_model_lanes(
            provider,
            distinguish_runtime_settings=True,
        )
        normalized_batches = normalize_merged_image_batches(batches)
        prompt, _ = resolve_merged_image_prompt(
            provider_lanes[0][0],
            image_task,
        )
        for candidate in (
            candidate for lane in provider_lanes for candidate in lane
        ):
            resolve_merged_image_prompt(candidate, image_task)
        config = Config(timeout_seconds=timeout_seconds)
        for batch in normalized_batches:
            validate_image_group(batch)
        resolved_output_path = resolve_merged_image_output_path(
            normalized_batches,
            output_path=output_path,
        )
        state_path = resolve_resume_state_path(resolved_output_path)
        with claim_output_target(resolved_output_path):
            markdown = read_repair_markdown(
                resolved_output_path,
                state_path=state_path,
            )
            markers = parse_merged_image_failure_markers(
                markdown,
                normalized_batches,
            )
            return repair_marked_image_batches(
                normalized_batches,
                markers=markers,
                markdown=markdown,
                provider_lanes=provider_lanes,
                prompt=prompt,
                image_task=image_task,
                output_path=resolved_output_path,
                config=config,
            )
    except OCRLLMError as error:
        public_error = error
    clear_public_error(public_error)
    raise public_error from None
