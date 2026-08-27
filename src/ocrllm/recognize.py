"""Validate, route, and execute one recognition request."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from .config import Config
from .errors import Cancelled, ConfigError, OCRLLMError, OutputError, ResumeStateError
from .providers.dashscope.provider_settings import DashScopeSettings
from .providers.google_genai.provider_settings import GoogleGenAISettings
from .result import RecognitionResult

if TYPE_CHECKING:
    from .output.output_target_claims import OutputTargetClaims
    from .processor_output import ProcessorOutput


def recognize(
    source: str | Path | Sequence[str | Path],
    *,
    config: Config | None = None,
) -> RecognitionResult:
    """Recognize one image group, one PDF, or one short MP3."""
    from .clear_public_error import clear_public_error
    from .output.output_target_claims import OutputTargetClaims

    public_error: OCRLLMError | None = None
    try:
        with OutputTargetClaims() as output_claims:
            return _recognize(
                source,
                config=config,
                output_claims=output_claims,
            )
    except OCRLLMError as error:
        public_error = error

    clear_public_error(public_error)
    raise public_error from None


def _recognize(
    source: str | Path | Sequence[str | Path],
    *,
    config: Config | None,
    output_claims: OutputTargetClaims,
) -> RecognitionResult:
    from .build_recognition_result import build_recognition_result
    from .coerce_source_paths import coerce_source_paths
    from .imaging.snapshot_image_group import snapshot_image_group
    from .output.build_output_path import build_output_path
    from .output.write_markdown_atomically import write_markdown_atomically
    from .profiles.resolve_image_profile import resolve_image_profile
    from .providers.provider_request_start_gate import (
        reuse_or_create_provider_request_start_gate,
    )
    from .raise_if_cancelled import raise_if_cancelled
    from .validate_execution_image_count import validate_execution_image_count
    from .validate_same_type_group import validate_same_type_group

    from .validate_config import validate_config

    cfg = validate_config(config)
    source_paths = coerce_source_paths(source)
    media_type = validate_same_type_group(source_paths)
    output_path = None
    resume_identity = None
    resume_state = None
    resume_state_path = None
    slot_checkpoint = None
    completed_resume_reused = False
    provider_calls_attempted: int | None = None
    current_model_attempts = None
    processor_output: ProcessorOutput | None = None

    if media_type in {"image", "pdf"}:
        from .providers.validate_vision_provider_config import (
            validate_vision_provider_config,
        )

        try:
            validate_vision_provider_config(
                cfg,
                require_injected_callable=True,
            )
        except ConfigError as error:
            error._add_safe_detail("workflow_pass", "draft")
            error._add_safe_detail("provider_calls_attempted", 0)
            error._add_safe_detail(
                "model_attempts",
                (
                    {
                        "model": None,
                        "outcome": error.code,
                        "disposition": "fix_request",
                        "provider_calls_attempted": 0,
                    },
                ),
            )
            raise
        if media_type == "image":
            if type(cfg.provider) in {DashScopeSettings, GoogleGenAISettings}:
                from .snapshot_config import snapshot_config

                cfg = snapshot_config(cfg)
            try:
                raise_if_cancelled(cfg.cancellation)
            except Cancelled as error:
                error._add_safe_detail("provider_calls_attempted", 0)
                raise

    with reuse_or_create_provider_request_start_gate(
        cfg.execution.provider_request_start_interval_seconds
    ):
        if media_type == "image":
            profile = resolve_image_profile(cfg.profile)
            validate_execution_image_count(source_paths, config=cfg)
            try:
                output_path = build_output_path(
                    source_paths,
                    profile=profile,
                    config=cfg,
                )
                if output_path is not None:
                    output_claims.claim(output_path)
                    # The first existence check can become stale before ownership.
                    output_path = build_output_path(
                        source_paths,
                        profile=profile,
                        config=cfg,
                    )
                with snapshot_image_group(source_paths, config=cfg) as validated_paths:
                    checkpoint_enabled = (
                        output_path is not None
                        and (cfg.resume or _can_checkpoint_image(cfg))
                    )
                    if checkpoint_enabled:
                        assert output_path is not None
                        from .fingerprint_image_request import (
                            fingerprint_image_request,
                        )
                        from .fingerprint_image_sources import fingerprint_image_sources
                        from .output.load_image_resume_state import (
                            load_image_resume_state,
                        )
                        from .output.resolve_image_resume_state_path import (
                            resolve_image_resume_state_path,
                        )
                        from .output.validate_image_resume_state_output_pair import (
                            validate_image_resume_state_output_pair,
                        )
                        from .reuse_image_resume_state import reuse_image_resume_state

                        resume_state_path = resolve_image_resume_state_path(output_path)
                        if (
                            not cfg.resume
                            and os.path.lexists(resume_state_path)
                            and not resume_state_path.is_file()
                        ):
                            raise OutputError(
                                "The image resume state path is not a regular file.",
                                code="OUTPUT_PATH_INVALID",
                            ) from None
                        resume_identity = fingerprint_image_request(
                            fingerprint_image_sources(source_paths, validated_paths),
                            profile=profile,
                            config=cfg,
                        )
                        resume_state = (
                            load_image_resume_state(resume_state_path)
                            if cfg.resume
                            else None
                        )
                        if cfg.resume:
                            validate_image_resume_state_output_pair(
                                resume_state,
                                output_path,
                            )
                        if (
                            cfg.resume
                            and resume_state is not None
                            and resume_state.markdown
                        ):
                            processor_output = reuse_image_resume_state(
                                resume_state,
                                resume_identity,
                            )
                            completed_resume_reused = True
                            raise_if_cancelled(cfg.cancellation)
                        else:
                            from .image_slot_checkpoint import ImageSlotCheckpoint
                            from .output.save_image_resume_state_atomically import (
                                save_image_resume_state_atomically,
                            )
                            from .recognize_validated_images import (
                                recognize_validated_images,
                            )

                            seeded_slots = ()
                            seeded_provider_client_closed: bool | None = True
                            if cfg.resume and resume_state is not None:
                                from .validate_image_resume_identity import (
                                    validate_image_resume_identity,
                                )

                                validate_image_resume_identity(
                                    resume_state,
                                    resume_identity,
                                )
                                raise_if_cancelled(cfg.cancellation)
                                seeded_slots = resume_state.slots
                                saved_client_closed = resume_state.metadata.get(
                                    "provider_client_closed"
                                )
                                seeded_provider_client_closed = (
                                    saved_client_closed
                                    if type(saved_client_closed) is bool
                                    else None
                                )
                            slot_checkpoint = ImageSlotCheckpoint(
                                resume_identity,
                                persist_state=lambda state: (
                                    save_image_resume_state_atomically(
                                        resume_state_path,
                                        state,
                                    )
                                ),
                                profile=profile,
                                snapshot_paths=tuple(validated_paths),
                                seeded_slots=seeded_slots,
                                seeded_provider_client_closed=(
                                    seeded_provider_client_closed
                                ),
                            )
                            processor_output = recognize_validated_images(
                                validated_paths,
                                profile=profile,
                                config=cfg,
                                slot_checkpoint=slot_checkpoint,
                            )
                    else:
                        from .recognize_validated_images import (
                            recognize_validated_images,
                        )

                        processor_output = recognize_validated_images(
                            validated_paths,
                            profile=profile,
                            config=cfg,
                        )

                    provider_calls_attempted = (
                        0 if completed_resume_reused else None
                    )
                    if not completed_resume_reused:
                        model_attempts = processor_output.metadata.get("model_attempts")
                        if type(model_attempts) is tuple:
                            attempt_counts: list[int] = []
                            for attempt in model_attempts:
                                if not isinstance(attempt, Mapping):
                                    break
                                count = attempt.get("provider_calls_attempted")
                                if type(count) is not int or count < 0:
                                    break
                                attempt_counts.append(count)
                            else:
                                provider_calls_attempted = sum(attempt_counts)
                                current_model_attempts = model_attempts
                        if provider_calls_attempted is None:
                            fallback_count = processor_output.metadata.get(
                                "provider_call_count"
                            )
                            if type(fallback_count) is int and fallback_count >= 0:
                                provider_calls_attempted = fallback_count
                    if provider_calls_attempted is not None:
                        from dataclasses import replace

                        current_metadata = dict(processor_output.metadata)
                        current_metadata["current_run_provider_call_count"] = (
                            provider_calls_attempted
                        )
                        processor_output = replace(
                            processor_output,
                            metadata=current_metadata,
                        )
            except (OutputError, ResumeStateError) as error:
                if provider_calls_attempted is not None:
                    error._add_safe_detail(
                        "provider_calls_attempted",
                        provider_calls_attempted,
                    )
                if current_model_attempts is not None:
                    error._add_safe_detail("model_attempts", current_model_attempts)
                if processor_output is not None:
                    if cfg.image_mode == "ocr":
                        from .attach_settled_local_ocr_evidence_to_error import (
                            attach_settled_local_ocr_evidence_to_error,
                        )

                        attach_settled_local_ocr_evidence_to_error(
                            error,
                            processor_output.metadata,
                        )
                    from .attach_current_model_token_usage_to_error import (
                        attach_current_model_token_usage_to_error,
                    )

                    attach_current_model_token_usage_to_error(
                        error,
                        processor_output.metadata.get("current_model_token_usage"),
                    )
                    if (
                        processor_output.metadata.get("provider_client_closed") is False
                        and "provider_client_closed" not in error.details
                    ):
                        error._add_safe_detail("provider_client_closed", False)
                raise
        elif media_type == "pdf":
            from .processors.recognize_pdf import recognize_pdf

            processor_output, output_path = recognize_pdf(
                source_paths,
                config=cfg,
                output_claims=output_claims,
            )
            pdf_calls = processor_output.metadata.get(
                "current_run_provider_call_count"
            )
            if type(pdf_calls) is int and pdf_calls >= 0:
                provider_calls_attempted = pdf_calls
        else:
            from .validate_google_mp3_options import validate_google_mp3_options

            validate_google_mp3_options(source_paths, config=cfg)
            from .processors.recognize_short_mp3 import recognize_validated_short_mp3

            processor_output = recognize_validated_short_mp3(
                source_paths[0],
                config=cfg,
            )

    assert processor_output is not None
    try:
        if media_type in {"image", "pdf"}:
            raise_if_cancelled(cfg.cancellation)
        if output_path is not None and resume_identity is not None:
            # The state file is kept after publication: it is what lets a repeated
            # call, and therefore a repeated batch, skip work that was already paid for.
            assert output_path is not None
            assert resume_identity is not None
            assert resume_state_path is not None
            if slot_checkpoint is not None:
                from .build_image_resume_state import build_image_resume_state
                from .output.save_image_resume_state_atomically import (
                    save_image_resume_state_atomically,
                )

                resume_state = build_image_resume_state(
                    resume_identity,
                    processor_output,
                    slots=slot_checkpoint.slots,
                )
                save_image_resume_state_atomically(resume_state_path, resume_state)
                raise_if_cancelled(cfg.cancellation)
            if cfg.resume and output_path.exists():
                from .output.validate_image_resume_output import (
                    validate_image_resume_output,
                )

                validate_image_resume_output(output_path, resume_state)
            else:
                write_markdown_atomically(
                    output_path,
                    processor_output.markdown,
                    overwrite=cfg.overwrite,
                )
        elif output_path is not None:
            write_markdown_atomically(
                output_path,
                processor_output.markdown,
                overwrite=cfg.overwrite or (media_type == "pdf" and cfg.resume),
            )
        result = build_recognition_result(
            processor_output,
            output_path=output_path,
        )
    except (Cancelled, OutputError, ResumeStateError) as error:
        if provider_calls_attempted is not None:
            error._add_safe_detail(
                "provider_calls_attempted",
                provider_calls_attempted,
            )
        if current_model_attempts is not None:
            error._add_safe_detail("model_attempts", current_model_attempts)
        from .attach_current_model_token_usage_to_error import (
            attach_current_model_token_usage_to_error,
        )

        attach_current_model_token_usage_to_error(
            error,
            processor_output.metadata.get("current_model_token_usage"),
        )
        if cfg.image_mode == "ocr":
            from .attach_settled_local_ocr_evidence_to_error import (
                attach_settled_local_ocr_evidence_to_error,
            )

            attach_settled_local_ocr_evidence_to_error(
                error,
                processor_output.metadata,
            )
        if processor_output.metadata.get("provider_client_closed") is False:
            error._add_safe_detail("provider_client_closed", False)
        raise
    return result


def _can_checkpoint_image(config: Config) -> bool:
    """Return whether this provider has a stable identity for automatic reuse."""
    if config.image_mode == "ocr":
        return True
    if type(config.provider) in {DashScopeSettings, GoogleGenAISettings}:
        return True
    try:
        identity = getattr(config.provider, "resume_identity", None)
    except Exception:
        return False
    return type(identity) is str and bool(identity.strip())
