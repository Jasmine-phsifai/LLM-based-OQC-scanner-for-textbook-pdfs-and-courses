"""Recognize one validated long MP3 through native Google Files."""

from __future__ import annotations

from pathlib import Path

from ..audio.snapshot_long_mp3 import snapshot_long_mp3
from ..audio.transcription_prompt import AUDIO_TRANSCRIPTION_PROMPT
from ..config import Config
from ..errors import OutputError
from ..processor_output import ProcessorOutput
from ..providers.google_genai.recognize_uploaded_mp3 import recognize_uploaded_mp3
from ..raise_if_cancelled import raise_if_cancelled
from .build_long_mp3_processor_output import build_long_mp3_processor_output


def recognize_validated_long_mp3(source_path: Path, *, config: Config) -> ProcessorOutput:
    """Own one long MP3, settle one Files lifecycle, and keep the result in memory."""
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
