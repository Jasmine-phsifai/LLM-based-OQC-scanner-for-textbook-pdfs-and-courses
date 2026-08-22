"""Validate, route, and execute one recognition request."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from .config import Config
from .errors import OCRLLMError, OutputError

if TYPE_CHECKING:
    from .result import RecognitionResult


def recognize(
    source: str | Path | Sequence[str | Path],
    *,
    config: Config | None = None,
) -> RecognitionResult:
    """Recognize one image or one ordered same-context image group."""
    public_error: OCRLLMError | None = None
    try:
        return _recognize(source, config=config)
    except OCRLLMError as error:
        public_error = error

    public_error.__cause__ = None
    public_error.__context__ = None
    public_error.__suppress_context__ = True
    public_error.__traceback__ = None
    raise public_error from None


def _recognize(
    source: str | Path | Sequence[str | Path],
    *,
    config: Config | None,
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
    from .validate_execution_image_count import validate_execution_image_count
    from .validate_same_type_group import validate_same_type_group

    from .validate_config import validate_config

    cfg = validate_config(config)
    profile = resolve_image_profile(cfg.profile)
    source_paths = coerce_source_paths(source)
    validate_execution_image_count(source_paths, config=cfg)
    media_type = validate_same_type_group(source_paths)
    output_path = None
    resume_identity = None
    resume_state = None
    resume_state_path = None
    slot_checkpoint = None

    with reuse_or_create_provider_request_start_gate(
        cfg.execution.provider_request_start_interval_seconds
    ):
        if media_type == "image":
            with snapshot_image_group(source_paths, config=cfg) as validated_paths:
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
                    from .fingerprint_image_request import fingerprint_image_request
                    from .fingerprint_image_sources import fingerprint_image_sources
                    from .output.load_image_resume_state import load_image_resume_state
                    from .reuse_image_resume_state import reuse_image_resume_state

                    # The sibling suffix is a durable persistence convention.
                    resume_state_path = output_path.with_name(
                        f"{output_path.stem}.ocrllm-state.json"
                    )
                    if (
                        not cfg.resume
                        and resume_state_path.exists()
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
                        from .errors import ResumeStateError

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
                            seeded_slots = resume_state.slots
                        slot_checkpoint = ImageSlotCheckpoint(
                            resume_identity,
                            resume_state_path,
                            profile=profile,
                            seeded_slots=seeded_slots,
                        )
                        processor_output = recognize_validated_images(
                            validated_paths,
                            profile=profile,
                            config=cfg,
                            slot_checkpoint=slot_checkpoint,
                        )
                else:
                    from .recognize_validated_images import recognize_validated_images

                    processor_output = recognize_validated_images(
                        validated_paths,
                        profile=profile,
                        config=cfg,
                    )
        else:  # pragma: no cover - routing is closed until another phase is authorized.
            raise AssertionError(f"unhandled validated media type: {media_type}")

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
            overwrite=cfg.overwrite,
        )
    return build_recognition_result(processor_output, output_path=output_path)


def _can_checkpoint_image(config: Config) -> bool:
    """Return whether this provider has a stable identity for automatic reuse."""
    if config.image_mode == "ocr":
        return True
    if type(config.provider).__name__ == "DashScopeSettings":
        return True
    try:
        identity = getattr(config.provider, "resume_identity", None)
    except Exception:
        return False
    return type(identity) is str and bool(identity.strip())
