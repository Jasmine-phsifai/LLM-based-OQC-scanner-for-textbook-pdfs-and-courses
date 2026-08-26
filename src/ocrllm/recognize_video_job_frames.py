"""Recognize or reuse every retained frame group in one video job."""

from __future__ import annotations

from dataclasses import replace

from .attach_current_video_evidence_to_error import (
    attach_current_video_evidence_to_error,
)
from .attach_video_frame_group_identity import attach_video_frame_group_identity
from .batch_item_outcome import BatchItemOutcome
from .build_image_resume_state import build_image_resume_state
from .build_recognition_result import build_recognition_result
from .config import Config
from .errors import OCRLLMError
from .fingerprint_image_request import fingerprint_image_request
from .fingerprint_image_sources import fingerprint_image_sources
from .group_retained_video_frames import group_retained_video_frames
from .image_slot_checkpoint import ImageSlotCheckpoint
from .imaging.snapshot_image_group import snapshot_image_group
from .profiles.resolve_image_profile import resolve_image_profile
from .providers.provider_request_start_gate import (
    reuse_or_create_provider_request_start_gate,
)
from .recognize_validated_images import recognize_validated_images
from .retained_video_frame import RetainedVideoFrame
from .reuse_image_resume_state import reuse_image_resume_state
from .validate_image_resume_identity import validate_image_resume_identity
from .video_job_journal import VideoJobJournal


def recognize_video_job_frames(
    frames: tuple[RetainedVideoFrame, ...],
    *,
    config: Config,
    journal: VideoJobJournal,
) -> tuple[BatchItemOutcome, ...]:
    """Settle frame groups serially and save each paid workflow slot."""
    profile = resolve_image_profile(config.profile)
    planned_groups = journal.state.frame_groups
    grouped_frames = group_retained_video_frames(
        frames,
        len(planned_groups[0].frame_indices),
    )
    if len(grouped_frames) != len(planned_groups) or any(
        tuple(frame.frame_index for frame in frames_group) != planned.frame_indices
        or tuple(frame.timestamp_seconds for frame in frames_group)
        != planned.frame_timestamps_seconds
        for planned, frames_group in zip(planned_groups, grouped_frames, strict=True)
    ):
        from .errors import ResumeStateError

        raise ResumeStateError(
            "The retained video frame grouping no longer matches the journal.",
            code="RESUME_STATE_MISMATCH",
        ) from None

    outcomes: list[BatchItemOutcome] = []
    interval = config.execution.provider_request_start_interval_seconds
    try:
        with reuse_or_create_provider_request_start_gate(interval):
            for planned, frames_group in zip(
                planned_groups,
                grouped_frames,
                strict=True,
            ):
                source_paths = tuple(frame.path for frame in frames_group)
                with snapshot_image_group(
                    source_paths,
                    config=config,
                ) as snapshot_paths:
                    current_identity = fingerprint_image_request(
                        fingerprint_image_sources(source_paths, snapshot_paths),
                        profile=profile,
                        config=config,
                    )
                    if current_identity != planned.identity:
                        from .errors import ResumeStateError

                        raise ResumeStateError(
                            "A retained video frame group no longer matches the journal.",
                            code="RESUME_STATE_MISMATCH",
                        ) from None

                    saved = journal.state.frame_groups[planned.index].image_state
                    if saved is not None:
                        validate_image_resume_identity(saved, current_identity)
                    if saved is not None and saved.markdown:
                        output = _normalize_reused_output(
                            reuse_image_resume_state(saved, current_identity)
                        )
                        result = build_recognition_result(output, output_path=None)
                    else:
                        saved_client_closed = (
                            None
                            if saved is None
                            else saved.metadata.get("provider_client_closed")
                        )
                        checkpoint = ImageSlotCheckpoint(
                            current_identity,
                            persist_state=lambda state, index=planned.index: (
                                journal.persist_image_state(index, state)
                            ),
                            profile=profile,
                            snapshot_paths=tuple(snapshot_paths),
                            seeded_slots=() if saved is None else saved.slots,
                            seeded_provider_client_closed=(
                                True
                                if saved is None
                                else (
                                    saved_client_closed
                                    if type(saved_client_closed) is bool
                                    else None
                                )
                            ),
                        )
                        output = recognize_validated_images(
                            snapshot_paths,
                            profile=profile,
                            config=config,
                            slot_checkpoint=checkpoint,
                        )
                        output = _normalize_fresh_output(output)
                        result = build_recognition_result(output, output_path=None)
                        try:
                            completed_state = build_image_resume_state(
                                current_identity,
                                output,
                                slots=checkpoint.slots,
                            )
                            journal.persist_image_state(
                                planned.index,
                                completed_state,
                            )
                        except OCRLLMError as error:
                            attach_current_video_evidence_to_error(
                                error,
                                before=(result,),
                                primary_provider_calls_attempted=0,
                            )
                            raise

                outcome = BatchItemOutcome(
                    index=planned.index,
                    result=result,
                )
                outcomes.append(
                    attach_video_frame_group_identity(outcome, frames_group)
                )
    except OCRLLMError as error:
        attach_current_video_evidence_to_error(
            error,
            before=tuple(
                outcome.result
                for outcome in outcomes
                if outcome.result is not None
            ),
        )
        raise
    return tuple(outcomes)


def _normalize_fresh_output(output):
    calls = output.metadata.get("provider_call_count")
    metadata = dict(output.metadata)
    if type(calls) is int and calls >= 0:
        metadata["current_run_provider_call_count"] = calls
    return replace(output, metadata=metadata)


def _normalize_reused_output(output):
    metadata = dict(output.metadata)
    metadata["current_run_provider_call_count"] = 0
    metadata["current_model_token_usage"] = ()
    metadata.pop("model_attempts", None)
    workflow_slots = metadata.get("workflow_slots")
    if type(workflow_slots) is tuple:
        metadata["workflow_slots"] = tuple(
            {
                **dict(slot),
                "reused": True,
                "provider_calls_attempted": 0,
            }
            for slot in workflow_slots
        )
    return replace(output, metadata=metadata)
