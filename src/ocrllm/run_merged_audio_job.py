"""Own one fresh or resumed merged-audio job lifecycle."""

from __future__ import annotations

from pathlib import Path

from .audio.snapshot_product_mp3 import snapshot_product_mp3
from .audio_slice import AudioSlice
from .build_merged_audio_resume_state import build_merged_audio_resume_state
from .config import Config
from .errors import ResumeStateError
from .execute_merged_audio_plan import execute_merged_audio_plan
from .finalize_merged_audio_result import finalize_merged_audio_result
from .fingerprint_audio_snapshot import fingerprint_audio_snapshot
from .normalize_audio_slices import normalize_audio_slices
from .normalize_provider_model_lanes import normalize_provider_model_lanes
from .output.load_merged_audio_resume_state import load_merged_audio_resume_state
from .output.output_target_claims import OutputTargetClaims
from .output.preflight_resumable_markdown_output import (
    preflight_resumable_markdown_output,
)
from .output.resolve_merged_audio_output_path import (
    resolve_merged_audio_output_path,
)
from .output.resolve_resume_state_path import resolve_resume_state_path
from .output.save_merged_audio_resume_state_atomically import (
    save_merged_audio_resume_state_atomically,
)
from .providers.provider_model import ProviderModel
from .providers.validate_audio_provider_model import validate_audio_provider_model
from .resolve_audio_slice_mode import resolve_audio_slice_mode
from .result import RecognitionResult


def run_merged_audio_job(
    slices: tuple[AudioSlice, ...],
    *,
    provider: (
        ProviderModel
        | list[ProviderModel]
        | list[list[ProviderModel]]
    ),
    output_path: str | Path | None,
    timeout_seconds: float,
    resume: bool,
    overwrite: bool,
) -> RecognitionResult:
    """Validate, snapshot, settle, checkpoint, and publish one audio plan."""
    provider_lanes = normalize_provider_model_lanes(
        provider,
        distinguish_runtime_settings=True,
    )
    for candidate in (
        candidate for lane in provider_lanes for candidate in lane
    ):
        validate_audio_provider_model(candidate)
    slices = normalize_audio_slices(slices)
    Config(timeout_seconds=timeout_seconds, overwrite=overwrite)
    source_path = slices[0].source
    resolved_output_path = resolve_merged_audio_output_path(
        source_path,
        output_path=output_path,
    )
    state_path = resolve_resume_state_path(resolved_output_path)

    with snapshot_product_mp3(source_path) as snapshot:
        mode, interval_minutes, prompt_version = resolve_audio_slice_mode(
            slices,
            duration_seconds=snapshot.duration_seconds,
        )
        source = fingerprint_audio_snapshot(source_path, snapshot)
        requested_state = build_merged_audio_resume_state(
            slices,
            mode=mode,
            interval_minutes=interval_minutes,
            prompt_version=prompt_version,
            source=source,
        )
        with OutputTargetClaims() as claims:
            claims.claim(resolved_output_path)
            preflight_resumable_markdown_output(
                resolved_output_path,
                state_path,
                resume=resume,
                overwrite=False if resume else overwrite,
            )
            if resume:
                state = load_merged_audio_resume_state(state_path)
                _validate_resume_plan(state, requested_state)
                historical_usage = state.usage
            else:
                state = requested_state
                historical_usage = ()
                save_merged_audio_resume_state_atomically(state_path, state)
            (
                state,
                current_usage,
                reused_slot_count,
                provider_failures,
            ) = execute_merged_audio_plan(
                state,
                snapshot,
                provider_lanes=provider_lanes,
                state_path=state_path,
                timeout_seconds=timeout_seconds,
            )
            return finalize_merged_audio_result(
                state,
                output_path=resolved_output_path,
                state_path=state_path,
                current_usage=current_usage,
                historical_usage=historical_usage,
                reused_slot_count=reused_slot_count,
                provider_failures=provider_failures,
                overwrite=overwrite,
            )


def _validate_resume_plan(state, requested_state) -> None:
    if (
        state.mode != requested_state.mode
        or state.interval_minutes != requested_state.interval_minutes
        or state.prompt_version != requested_state.prompt_version
        or state.source != requested_state.source
        or tuple(_slot_identity(slot) for slot in state.slots)
        != tuple(_slot_identity(slot) for slot in requested_state.slots)
    ):
        raise ResumeStateError(
            "The supplied audio slices do not match the saved merged-audio plan.",
            code="RESUME_STATE_MISMATCH",
            details={"provider_calls_attempted": 0},
        ) from None


def _slot_identity(slot) -> tuple[int, float, float, float, float]:
    return (
        slot.index,
        slot.logical_start_seconds,
        slot.logical_end_seconds,
        slot.actual_start_seconds,
        slot.actual_end_seconds,
    )
