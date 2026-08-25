"""Validate, route, and execute one recognition request."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from .config import Config
from .errors import OCRLLMError, OutputError, ResumeStateError
from .providers.dashscope.provider_settings import DashScopeSettings
from .providers.google_genai.provider_settings import GoogleGenAISettings
from .result import RecognitionResult

if TYPE_CHECKING:
    from .output.output_target_claims import OutputTargetClaims


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

    with reuse_or_create_provider_request_start_gate(
        cfg.execution.provider_request_start_interval_seconds
    ):
        if media_type == "image":
            profile = resolve_image_profile(cfg.profile)
            validate_execution_image_count(source_paths, config=cfg)
            try:
                with snapshot_image_group(source_paths, config=cfg) as validated_paths:
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
                        from .reuse_image_resume_state import reuse_image_resume_state

                        # The sibling suffix is a durable persistence convention.
                        resume_state_path = output_path.with_name(
                            f"{output_path.stem}.ocrllm-state.json"
                        )
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
                        if cfg.resume and resume_state is None and output_path.exists():
                            raise ResumeStateError(
                                "Existing image output has no matching resume state.",
                                code="RESUME_STATE_INVALID",
                            ) from None
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
                            from .recognize_validated_images import (
                                recognize_validated_images,
                            )

                            seeded_slots = ()
                            if cfg.resume and resume_state is not None:
                                from .validate_image_resume_identity import (
                                    validate_image_resume_identity,
                                )

                                validate_image_resume_identity(
                                    resume_state,
                                    resume_identity,
                                )
                                if output_path.exists():
                                    raise ResumeStateError(
                                        "Existing image output conflicts with a partial "
                                        "resume state.",
                                        code="RESUME_STATE_MISMATCH",
                                    ) from None
                                raise_if_cancelled(cfg.cancellation)
                                seeded_slots = resume_state.slots
                            slot_checkpoint = ImageSlotCheckpoint(
                                resume_identity,
                                resume_state_path,
                                profile=profile,
                                snapshot_paths=tuple(validated_paths),
                                seeded_slots=seeded_slots,
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

    try:
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
    except (OutputError, ResumeStateError) as error:
        if provider_calls_attempted is not None:
            error._add_safe_detail(
                "provider_calls_attempted",
                provider_calls_attempted,
            )
        if current_model_attempts is not None:
            error._add_safe_detail("model_attempts", current_model_attempts)
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
