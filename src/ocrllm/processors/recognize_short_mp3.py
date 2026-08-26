"""Recognize one validated, bounded short MP3 through native Google GenAI."""

from __future__ import annotations

from pathlib import Path

from ..attach_current_model_token_usage_to_error import (
    attach_current_model_token_usage_to_error,
)
from ..audio.snapshot_short_mp3 import snapshot_short_mp3
from ..audio.transcription_prompt import AUDIO_TRANSCRIPTION_PROMPT
from ..config import Config
from ..errors import ConfigError, OutputError
from ..processor_output import ProcessorOutput
from ..providers.google_genai.recognize_short_mp3 import recognize_short_mp3
from ..raise_if_cancelled import raise_if_cancelled
from .build_short_mp3_processor_output import build_short_mp3_processor_output


def recognize_validated_short_mp3(source_path: Path, *, config: Config) -> ProcessorOutput:
    """Snapshot one MP3, call Google once, and return an in-memory result."""
    raise_if_cancelled(config.cancellation)
    from ..providers.google_genai.resolve_google_genai_credential import (
        resolve_google_genai_credential,
    )

    try:
        resolve_google_genai_credential(config.provider)
    except ConfigError as error:
        error._add_safe_detail("provider_calls_attempted", 0)
        raise
    provider_call_completed = False
    processor_output: ProcessorOutput | None = None
    try:
        with snapshot_short_mp3(source_path, temp_dir=config.temp_dir) as snapshot:
            response = recognize_short_mp3(
                snapshot,
                prompt=AUDIO_TRANSCRIPTION_PROMPT,
                config=config,
            )
            provider_call_completed = True
            processor_output = build_short_mp3_processor_output(
                snapshot,
                response,
                config=config,
            )
        assert processor_output is not None
        return processor_output
    except OutputError as error:
        if (
            provider_call_completed
            and "provider_calls_attempted" not in error.details
        ):
            error._add_safe_detail("provider_calls_attempted", 1)
        if processor_output is not None:
            attach_current_model_token_usage_to_error(
                error,
                processor_output.metadata.get("current_model_token_usage"),
            )
            client_closed = processor_output.metadata.get(
                "provider_client_closed"
            )
            if (
                type(client_closed) is bool
                and "provider_client_closed" not in error.details
            ):
                error._add_safe_detail("provider_client_closed", client_closed)
        raise
