"""Recognize one ordered image group with the board profile."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from ..config import Config
from ..errors import AllCandidatesExhausted, OCRLLMError, ProviderError
from ..image_slot_state import ImageSlotState
from ..processor_output import ProcessorOutput
from ..profiles.build_board_consensus_prompt import build_board_consensus_prompt
from ..profiles.build_board_prompt import BOARD_PROMPT_VERSION, build_board_prompt
from ..profiles.build_board_review_prompt import build_board_review_prompt
from ..profiles.build_board_sign_scout_prompt import (
    SIGN_SCOUT_PROMPT_VERSION,
    build_board_sign_scout_prompt,
)
from ..profiles.build_board_symbol_audit_prompt import build_board_symbol_audit_prompt
from ..providers.call_vision_provider import call_vision_provider
from ..provider_error_disposition import get_provider_error_disposition
from ..providers.dashscope.resolve_sign_scout_enable_thinking import (
    resolve_sign_scout_enable_thinking,
)
from ..providers.dashscope.resolve_dashscope_model import DEFAULT_DASHSCOPE_MODEL
from ..providers.dashscope.provider_settings import DashScopeSettings
from ..providers.resolved_vision_provider import ResolvedVisionProvider
from ..providers.resolve_vision_provider import resolve_vision_provider
from ..snapshot_config import snapshot_config
from ..vision_model_settings import VisionModelSettings
from .restore_quorum_standalone_signs import restore_quorum_standalone_signs

if TYPE_CHECKING:
    from ..image_slot_checkpoint import ImageSlotCheckpoint


def recognize_images(
    image_paths: Sequence[Path],
    *,
    profile: str,
    config: Config,
    slot_checkpoint: ImageSlotCheckpoint | None = None,
) -> ProcessorOutput:
    """Recognize with the configured model queue and disclose every attempt."""
    candidates = config.vision_model.candidate_models
    if candidates:
        ordered_models = list(candidates)
        if config.vision_model.name is not None:
            ordered_models.insert(0, config.vision_model.name)
        ordered_models = list(dict.fromkeys(ordered_models))
    else:
        ordered_models = [config.vision_model.name]

    attempts: list[dict[str, str | int]] = []
    for candidate_index, model in enumerate(ordered_models):
        candidate_config = config
        if model is not None:
            candidate_config = replace(
                config,
                vision_model=replace(
                    config.vision_model,
                    name=model,
                    candidate_models=(),
                ),
            )
        try:
            output = _recognize_images_once(
                image_paths,
                profile=profile,
                config=candidate_config,
                slot_checkpoint=slot_checkpoint,
            )
        except ProviderError as error:
            disposition = get_provider_error_disposition(error)
            attempts.append(
                {
                    "model": model or "",
                    "outcome": error.code,
                    "disposition": disposition.action,
                    "provider_calls_attempted": error.details.get(
                        "provider_calls_attempted", 1
                    ),
                }
            )
            if error.code != "PROVIDER_QUOTA_EXHAUSTED" or candidate_index == len(ordered_models) - 1:
                error._add_safe_detail("model_attempts", attempts)
                if error.code == "PROVIDER_QUOTA_EXHAUSTED" and candidate_index == len(ordered_models) - 1:
                    error = AllCandidatesExhausted(
                        "All configured model candidates were exhausted.",
                        details=dict(error.details),
                    )
                    error._add_safe_detail("all_candidates_exhausted", True)
                    error._add_safe_detail("last_model", model)
                raise error from None
            continue

        attempts.append(
            {
                "model": model or "",
                "outcome": "success",
                "provider_calls_attempted": output.metadata["provider_call_count"],
            }
        )
        metadata = dict(output.metadata)
        metadata["model_attempts"] = attempts
        return replace(output, metadata=metadata)

    raise AssertionError("the model candidate loop must return or raise")


def _recognize_images_once(
    image_paths: Sequence[Path],
    *,
    profile: str,
    config: Config,
    slot_checkpoint: ImageSlotCheckpoint | None = None,
) -> ProcessorOutput:
    """Call one injected vision provider and reject false-success output."""
    if type(config.provider) is DashScopeSettings:
        config = snapshot_config(config)
    resolved_provider = resolve_vision_provider(config)
    base_prompt = build_board_prompt(config.input_languages, config.output_language)
    dashscope_settings = (
        config.provider if type(config.provider) is DashScopeSettings else None
    )
    scout_model = (
        dashscope_settings.standalone_sign_scout_model
        if dashscope_settings is not None
        else None
    )
    primary_prompt = (
        build_board_symbol_audit_prompt(base_prompt)
        if scout_model is not None
        else base_prompt
    )

    calls_dispatched = 0
    slot_ledger: list[dict[str, str | int | bool | None]] = []

    def run_pass(
        slot_id: str,
        resolved: ResolvedVisionProvider,
        pass_config: Config,
        prompt: str,
    ) -> str:
        """Reuse, or pay for and persist, one workflow pass."""
        nonlocal calls_dispatched
        if slot_checkpoint is not None:
            persisted = slot_checkpoint.reusable_slot(
                slot_id,
                provider=resolved.name,
                model=resolved.model,
            )
            if persisted is not None:
                slot_ledger.append(
                    {
                        "slot_id": persisted.slot_id,
                        "workflow_pass": persisted.workflow_pass,
                        "provider": persisted.provider,
                        "model": persisted.model,
                        "reused": True,
                        "provider_calls_attempted": 0,
                    }
                )
                return persisted.markdown
        try:
            markdown = call_vision_provider(
                resolved,
                image_paths,
                prompt=prompt,
                config=pass_config,
            )
        except OCRLLMError as error:
            error._add_safe_detail("workflow_pass", slot_id)
            error._add_safe_detail("provider_calls_attempted", calls_dispatched + 1)
            raise
        calls_dispatched += 1
        if slot_checkpoint is not None:
            slot_checkpoint.persist_slot(
                ImageSlotState(
                    slot_id=slot_id,
                    workflow_pass=slot_id,
                    provider=resolved.name,
                    model=resolved.model,
                    markdown=markdown,
                    markdown_sha256=hashlib.sha256(
                        markdown.encode("utf-8")
                    ).hexdigest(),
                    provider_calls_attempted=calls_dispatched,
                )
            )
        slot_ledger.append(
            {
                "slot_id": slot_id,
                "workflow_pass": slot_id,
                "provider": resolved.name,
                "model": resolved.model,
                "reused": False,
                "provider_calls_attempted": calls_dispatched,
            }
        )
        return markdown

    drafts: list[str] = []
    for candidate_index in range(config.preferences.draft_candidates):
        drafts.append(
            run_pass(
                "draft" if candidate_index == 0 else "draft_2",
                resolved_provider,
                config,
                primary_prompt,
            )
        )

    markdown = drafts[0]
    if config.preferences.review_passes:
        consensus = config.preferences.draft_candidates == 2
        review_prompt = (
            build_board_consensus_prompt(base_prompt, (drafts[0], drafts[1]))
            if consensus
            else build_board_review_prompt(base_prompt, drafts[0])
        )
        markdown = run_pass(
            "consensus_review" if consensus else "review",
            resolved_provider,
            config,
            review_prompt,
        )

    restored_sign_count = 0
    abstained_scout_count = 0
    scout_prompt: str | None = None
    if scout_model is not None:
        assert dashscope_settings is not None
        scout_enable_thinking = resolve_sign_scout_enable_thinking(scout_model)
        scout_config = replace(
            config,
            vision_model=VisionModelSettings(name=scout_model),
            provider=replace(
                dashscope_settings,
                enable_thinking=scout_enable_thinking,
                standalone_sign_scout_model=None,
            ),
        )
        resolved_scout = resolve_vision_provider(scout_config)
        scout_prompt = build_board_sign_scout_prompt(markdown)
        scouts: list[str] = []
        for scout_index in range(3):
            scouts.append(
                run_pass(
                    f"standalone_sign_scout_{scout_index + 1}",
                    resolved_scout,
                    scout_config,
                    scout_prompt,
                )
            )
        try:
            restored = restore_quorum_standalone_signs(
                markdown,
                tuple(scouts),
                minimum_agreement=2,
            )
        except ValueError:
            raise ProviderError(
                "The standalone-sign scout responses could not be merged safely.",
                code="PROVIDER_RESPONSE_INVALID",
                details={
                    "model": scout_model,
                    "provider": resolved_scout.name,
                    "provider_calls_attempted": calls_dispatched,
                    "workflow_pass": "standalone_sign_merge",
                },
            ) from None
        markdown = restored.markdown
        restored_sign_count = restored.restored_count
        abstained_scout_count = restored.abstained_scout_count

    metadata: dict[str, object] = {
        "image_count": len(image_paths),
        "model": resolved_provider.model,
        # Only the pinned v17-gated snapshot is proven; every other model is
        # selectable but unproven. Selection and proof status stay separate.
        "model_evidence": (
            "proven"
            if resolved_provider.model == DEFAULT_DASHSCOPE_MODEL
            else "unproven"
        ),
        "model_proven": resolved_provider.model == DEFAULT_DASHSCOPE_MODEL,
        "prompt_version": BOARD_PROMPT_VERSION,
        "provider": resolved_provider.name,
        "profile": profile,
        "provider_call_count": calls_dispatched,
        "workflow_slots": slot_ledger,
        "draft_candidates": config.preferences.draft_candidates,
        "review_passes": config.preferences.review_passes,
        "standalone_sign_scout_model": scout_model,
        "standalone_sign_scout_count": 3 if scout_model is not None else 0,
        "standalone_signs_restored": restored_sign_count,
        "standalone_sign_scout_abstention_count": abstained_scout_count,
        "standalone_sign_scout_prompt_version": (
            SIGN_SCOUT_PROMPT_VERSION if scout_prompt is not None else None
        ),
        "standalone_sign_scout_prompt_sha256": (
            hashlib.sha256(scout_prompt.encode("utf-8")).hexdigest()
            if scout_prompt is not None
            else None
        ),
        "standalone_sign_scout_prompt_utf8_bytes": (
            len(scout_prompt.encode("utf-8")) if scout_prompt is not None else None
        ),
    }
    if resolved_provider.name == "dashscope" and dashscope_settings is not None:
        metadata.update(
            {
                "provider_region": dashscope_settings.region,
                "enable_thinking": dashscope_settings.enable_thinking,
                "vl_high_resolution_images": (
                    dashscope_settings.vl_high_resolution_images
                ),
                "standalone_sign_scout_enable_thinking": (
                    scout_enable_thinking if scout_model is not None else None
                ),
            }
        )

    return ProcessorOutput(
        media_type="image",
        profile=profile,
        markdown=markdown,
        metadata=metadata,
    )
