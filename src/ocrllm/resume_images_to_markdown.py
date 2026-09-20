"""Resume unresolved slots in one merged-image Markdown job."""

from __future__ import annotations

from .observe_recognition import observed_stage

from pathlib import Path

from .providers.provider_model import ProviderModel
from .result import RecognitionResult


@observed_stage('resume', 'ocr')
def resume_images_to_markdown(
    batches: tuple[tuple[str | Path, ...], ...],
    *,
    provider: (
        ProviderModel
        | list[ProviderModel]
        | list[list[ProviderModel]]
    ),
    output_path: str | Path | None = None,
    timeout_seconds: float = 120.0,
    stop_requested: object | None = None,
    service_recovery_only: bool = False,
    service_recovery_batch_id: str | None = None,
) -> RecognitionResult:
    """Restore the plan; optionally retry only saved service failures.

    Other failures and unresolved slots are excluded, including validation
    failures produced before a pause. The caller owns the bounded recovery
    campaign. A nonempty service_recovery_batch_id is required in this mode;
    each slot is atomically reserved once for that ID before dispatch. Pauses or
    unknown crashes do not refund reservations. Provider retry rules remain
    bounded and drain still prevents new retries/fallbacks after a stop.
    """
    from .build_merged_image_resume_state import build_merged_image_resume_state
    from .clear_public_error import clear_public_error
    from .config import Config
    from .errors import OCRLLMError
    from .execute_merged_image_plan import execute_merged_image_plan
    from .finalize_merged_image_result import finalize_merged_image_result
    from .fingerprint_merged_image_batches import fingerprint_merged_image_batches
    from .normalize_merged_image_batches import normalize_merged_image_batches
    from .normalize_provider_model_lanes import normalize_provider_model_lanes
    from .output.load_merged_image_resume_state import load_merged_image_resume_state
    from .output.output_target_claims import OutputTargetClaims
    from .output.preflight_resumable_markdown_output import (
        preflight_resumable_markdown_output,
    )
    from .output.resolve_resume_state_path import resolve_resume_state_path
    from .output.resolve_merged_image_output_path import (
        resolve_merged_image_output_path,
    )
    from .resolve_merged_image_prompt import resolve_merged_image_prompt

    public_error: OCRLLMError | None = None
    try:
        if type(service_recovery_only) is not bool:
            from .errors import ConfigError
            raise ConfigError("service_recovery_only must be bool.", code="CONFIG_INVALID")
        if service_recovery_only:
            from .inspect_image_service_recovery import validate_service_recovery_batch_id
            validate_service_recovery_batch_id(service_recovery_batch_id)
        elif service_recovery_batch_id is not None:
            from .errors import ConfigError
            raise ConfigError("Service recovery batch ID requires service_recovery_only.", code="CONFIG_INVALID")
        provider_lanes = normalize_provider_model_lanes(
            provider,
            distinguish_runtime_settings=True,
        )
        normalized_batches = normalize_merged_image_batches(batches)
        resolved_output_path = resolve_merged_image_output_path(
            normalized_batches,
            output_path=output_path,
        )
        state_path = resolve_resume_state_path(resolved_output_path)
        Config(timeout_seconds=timeout_seconds, cancellation=stop_requested)
        with OutputTargetClaims() as claims:
            claims.claim(resolved_output_path)
            preflight_resumable_markdown_output(
                resolved_output_path,
                state_path,
                resume=True,
                overwrite=False,
            )
            state = load_merged_image_resume_state(state_path)
            selected_slot_indexes = None
            if service_recovery_only:
                from .inspect_image_service_recovery import image_service_recovery_slots
                from .errors import ResumeStateError
                if state.provider_cleanup_failed:
                    raise ResumeStateError(
                        "Image service recovery requires confirmed provider cleanup.",
                        code="RESUME_STATE_INVALID", details={"provider_calls_attempted": 0},
                    )
                selected_slot_indexes = image_service_recovery_slots(state, service_recovery_batch_id)
            prompt, prompt_version = resolve_merged_image_prompt(
                provider_lanes[0][0],
                state.image_task,
            )
            for candidate in (
                candidate for lane in provider_lanes for candidate in lane
            ):
                resolve_merged_image_prompt(candidate, state.image_task)
            sources = fingerprint_merged_image_batches(normalized_batches)
            requested_plan = build_merged_image_resume_state(
                normalized_batches,
                image_task=state.image_task,
                prompt_version=prompt_version,
                sources=sources,
            )
            _validate_resume_plan(state, requested_plan)
            historical_usage = state.usage
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
                stop_requested=stop_requested,
                selected_slot_indexes=selected_slot_indexes,
                service_recovery_batch_id=service_recovery_batch_id,
            )
            return finalize_merged_image_result(
                state,
                output_path=resolved_output_path,
                state_path=state_path,
                current_usage=current_usage,
                historical_usage=historical_usage,
                reused_slot_count=reused_slot_count,
                provider_failures=provider_failures,
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
