"""Recognize one validated long MP3 through native Google Files."""

from __future__ import annotations

from pathlib import Path

from ..audio.load_long_audio_partial_state import load_long_audio_partial_state
from ..audio.plan_long_audio_output_paths import plan_long_audio_output_paths
from ..audio.preflight_long_audio_output_ownership import (
    preflight_long_audio_output_ownership,
)
from ..audio.remove_long_audio_temporary_state import (
    remove_long_audio_temporary_state,
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
from .recognize_long_mp3_intervals import recognize_long_mp3_intervals
from .recognize_long_mp3_whole import recognize_long_mp3_whole


def recognize_validated_long_mp3(
    source_path: Path,
    *,
    config: Config,
    interval_minutes: int | None = None,
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
            saved_state = None
            if config.resume:
                saved_state = load_long_audio_partial_state(paths.resume_state)
                if saved_state is None:
                    raise ResumeStateError(
                        "The long-audio resume state is missing or invalid.",
                        code="RESUME_STATE_INVALID",
                    ) from None
                if interval_minutes is None:
                    interval_minutes = saved_state.interval_minutes
            mode = "interval" if interval_minutes is not None else "whole"
            if saved_state is not None and (
                saved_state.mode != mode
                or saved_state.interval_minutes != interval_minutes
            ):
                raise ResumeStateError(
                    "The long-audio partial state belongs to a different mode.",
                    code="RESUME_STATE_MISMATCH",
                ) from None
            snapshot_context = (
                snapshot_long_mp3(
                    source_path,
                    temp_dir=config.temp_dir,
                    interval_mode=True,
                )
                if interval_minutes is not None
                else snapshot_long_mp3(source_path, temp_dir=config.temp_dir)
            )
            with snapshot_context as snapshot:
                model = config.audio_model.name
                assert type(model) is str
                if interval_minutes is not None:
                    processor_output, current_run_calls = recognize_long_mp3_intervals(
                        snapshot,
                        config=config,
                        interval_minutes=interval_minutes,
                        state_path=paths.resume_state,
                        saved_state=saved_state,
                    )
                else:
                    processor_output, current_run_calls = recognize_long_mp3_whole(
                        snapshot,
                        config=config,
                        state_path=paths.resume_state,
                        saved_state=saved_state,
                    )
            write_markdown_atomically(
                paths.result,
                processor_output.markdown,
                overwrite=False,
            )
            processor_output = remove_long_audio_temporary_state(
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
