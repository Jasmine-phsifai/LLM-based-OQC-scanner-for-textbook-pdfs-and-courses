"""Recognize one validated long MP3 through native Google Files."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..audio.fingerprint_long_audio_request import (
    LONG_AUDIO_REQUEST_IDENTITY_VERSION,
    fingerprint_long_audio_request,
)
from ..audio.load_long_audio_partial_state import load_long_audio_partial_state
from ..audio.long_audio_partial_state import (
    LONG_AUDIO_PARTIAL_STATE_VERSION,
    LongAudioPartialState,
)
from ..audio.long_audio_settled_slot import LongAudioSettledSlot
from ..audio.plan_long_audio_output_paths import plan_long_audio_output_paths
from ..audio.preflight_long_audio_output_ownership import (
    preflight_long_audio_output_ownership,
)
from ..audio.reuse_long_audio_partial_state import reuse_long_audio_partial_state
from ..audio.save_long_audio_partial_state_atomically import (
    save_long_audio_partial_state_atomically,
)
from ..audio.snapshot_long_mp3 import snapshot_long_mp3
from ..audio.transcription_prompt import AUDIO_TRANSCRIPTION_PROMPT
from ..config import Config
from ..errors import OCRLLMError, OutputError, OutputExists, ResumeStateError
from ..output.claim_output_target import claim_output_target
from ..output.write_markdown_atomically import write_markdown_atomically
from ..processor_output import ProcessorOutput
from ..providers.google_genai.recognize_uploaded_mp3 import recognize_uploaded_mp3
from ..raise_if_cancelled import raise_if_cancelled
from .build_long_mp3_processor_output import build_long_mp3_processor_output


def recognize_validated_long_mp3(
    source_path: Path,
    *,
    config: Config,
) -> tuple[ProcessorOutput, Path | None]:
    """Settle one Files request and optionally publish resumable Markdown."""
    output_dir = config.output_directory()
    if output_dir is None:
        return _recognize_in_memory(source_path, config=config), None

    raise_if_cancelled(config.cancellation)
    paths = plan_long_audio_output_paths(source_path, output_dir)
    with claim_output_target(paths.root):
        preflight_long_audio_output_ownership(paths, resume=config.resume)
        created_root = False
        current_run_calls = 0
        try:
            if not config.resume:
                _create_output_root(paths.root)
                created_root = True
            with snapshot_long_mp3(source_path, temp_dir=config.temp_dir) as snapshot:
                model = config.audio_model.name
                assert type(model) is str
                request_fingerprint = fingerprint_long_audio_request(
                    source_sha256=snapshot.sha256,
                    mode="whole",
                    provider="google",
                    model=model,
                    transport="google_files",
                )
                request_plan = (request_fingerprint,)
                slots: tuple[LongAudioSettledSlot, ...] = ()
                if config.resume:
                    saved_state = load_long_audio_partial_state(paths.resume_state)
                    if saved_state is None:
                        raise ResumeStateError(
                            "The long-audio resume state is missing or invalid.",
                            code="RESUME_STATE_INVALID",
                        ) from None
                    slots = reuse_long_audio_partial_state(saved_state, request_plan)
                if slots:
                    processor_output = _build_reused_output(
                        snapshot,
                        slots[0],
                    )
                else:
                    response = recognize_uploaded_mp3(
                        snapshot,
                        prompt=AUDIO_TRANSCRIPTION_PROMPT,
                        config=config,
                    )
                    current_run_calls = 1
                    processor_output = _with_current_run_count(
                        build_long_mp3_processor_output(snapshot, response, config=config),
                        count=1,
                    )
                    slot = _build_settled_slot(
                        processor_output,
                        request_fingerprint=request_fingerprint,
                    )
                    save_long_audio_partial_state_atomically(
                        paths.resume_state,
                        LongAudioPartialState(
                            state_version=LONG_AUDIO_PARTIAL_STATE_VERSION,
                            identity_version=LONG_AUDIO_REQUEST_IDENTITY_VERSION,
                            request_fingerprints=request_plan,
                            slots=(slot,),
                        ),
                    )
            write_markdown_atomically(
                paths.result,
                processor_output.markdown,
                overwrite=False,
            )
            processor_output = _remove_temporary_state(
                paths.resume_state,
                processor_output,
            )
            return processor_output, paths.result
        except OCRLLMError as error:
            if "provider_calls_attempted" not in error.details:
                error._add_safe_detail("provider_calls_attempted", current_run_calls)
            _remove_empty_new_root(paths.root, created=created_root)
            raise


def _recognize_in_memory(source_path: Path, *, config: Config) -> ProcessorOutput:
    """Keep the established no-output-directory behavior."""
    raise_if_cancelled(config.cancellation)
    provider_call_completed = False
    response = None
    try:
        with snapshot_long_mp3(source_path, temp_dir=config.temp_dir) as snapshot:
            response = recognize_uploaded_mp3(
                snapshot,
                prompt=AUDIO_TRANSCRIPTION_PROMPT,
                config=config,
            )
            provider_call_completed = True
            return build_long_mp3_processor_output(
                snapshot,
                response,
                config=config,
            )
    except OutputError as error:
        if provider_call_completed and "provider_calls_attempted" not in error.details:
            error._add_safe_detail("provider_calls_attempted", 1)
        if response is not None:
            if not response.remote_file_deleted:
                error._add_safe_detail("provider_file_cleanup_failed", True)
            if not response.client_closed:
                error._add_safe_detail("provider_client_cleanup_failed", True)
        raise


def _build_settled_slot(
    output: ProcessorOutput,
    *,
    request_fingerprint: str,
) -> LongAudioSettledSlot:
    usage = output.metadata["current_model_token_usage"][0]
    return LongAudioSettledSlot(
        window_index=0,
        request_fingerprint=request_fingerprint,
        markdown=output.markdown,
        markdown_sha256=hashlib.sha256(output.markdown.encode("utf-8")).hexdigest(),
        provider=output.metadata["provider"],
        model=output.metadata["model"],
        transport=output.metadata["transport"],
        provider_calls_attempted=output.metadata["provider_call_count"],
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        status=output.status,
        warnings=output.warnings,
        provider_file_cleanup_succeeded=output.metadata["remote_file_deleted"],
        provider_client_cleanup_succeeded=output.metadata["provider_client_closed"],
    )


def _build_reused_output(snapshot, slot: LongAudioSettledSlot) -> ProcessorOutput:
    return ProcessorOutput(
        media_type="audio",
        markdown=slot.markdown,
        status=slot.status,
        warnings=slot.warnings,
        metadata={
            "provider": slot.provider,
            "model": slot.model,
            "transport": slot.transport,
            "provider_call_count": slot.provider_calls_attempted,
            "current_run_provider_call_count": 0,
            "current_model_token_usage": (),
            "historical_model_token_usage": (
                {
                    "model": slot.model,
                    "input_tokens": slot.input_tokens,
                    "output_tokens": slot.output_tokens,
                },
            ),
            "duration_seconds": snapshot.duration_seconds,
            "byte_size": snapshot.byte_size,
            "remote_file_deleted": slot.provider_file_cleanup_succeeded,
            "provider_client_closed": slot.provider_client_cleanup_succeeded,
        },
    )


def _with_current_run_count(output: ProcessorOutput, *, count: int) -> ProcessorOutput:
    metadata = dict(output.metadata)
    metadata["current_run_provider_call_count"] = count
    return ProcessorOutput(
        media_type=output.media_type,
        markdown=output.markdown,
        status=output.status,
        warnings=output.warnings,
        metadata=metadata,
    )


def _remove_temporary_state(
    state_path: Path,
    output: ProcessorOutput,
) -> ProcessorOutput:
    try:
        state_path.unlink()
        return output
    except (OSError, ValueError):
        warning = "The temporary long-audio resume state could not be removed."
        metadata = dict(output.metadata)
        metadata["resume_state_removed"] = False
        return ProcessorOutput(
            media_type=output.media_type,
            markdown=output.markdown,
            status="partial",
            warnings=output.warnings + (warning,),
            metadata=metadata,
        )


def _remove_empty_new_root(root: Path, *, created: bool) -> None:
    if not created:
        return
    try:
        root.rmdir()
    except (OSError, ValueError):
        pass


def _create_output_root(root: Path) -> None:
    try:
        root.mkdir(parents=True, exist_ok=False)
    except FileExistsError as error:
        raise OutputExists(
            "The requested long-audio output directory already exists."
        ) from error
    except (OSError, ValueError) as error:
        raise OutputError(
            "The long-audio output directory could not be created.",
            code="OUTPUT_WRITE_FAILED",
        ) from error
