"""Recognize one validated, bounded short MP3 through native Google GenAI."""

from __future__ import annotations

from pathlib import Path

from ..audio.snapshot_short_mp3 import snapshot_short_mp3
from ..audio.transcription_prompt import AUDIO_TRANSCRIPTION_PROMPT
from ..config import Config
from ..errors import OutputError
from ..processor_output import ProcessorOutput
from ..providers.google_genai.recognize_short_mp3 import recognize_short_mp3
from ..raise_if_cancelled import raise_if_cancelled


def recognize_validated_short_mp3(source_path: Path, *, config: Config) -> ProcessorOutput:
    """Snapshot one MP3, call Google once, and return an in-memory result."""
    raise_if_cancelled(config.cancellation)
    provider_call_completed = False
    try:
        with snapshot_short_mp3(source_path, temp_dir=config.temp_dir) as snapshot:
            response = recognize_short_mp3(
                snapshot,
                prompt=AUDIO_TRANSCRIPTION_PROMPT,
                config=config,
            )
            provider_call_completed = True
            model = config.audio_model.name
            assert type(model) is str
            return ProcessorOutput(
                media_type="audio",
                markdown=response.markdown,
                metadata={
                    "provider": "google",
                    "model": model,
                    "provider_call_count": 1,
                    "current_model_token_usage": (
                        {
                            "model": model,
                            "input_tokens": response.input_tokens,
                            "output_tokens": response.output_tokens,
                        },
                    ),
                    "duration_seconds": snapshot.duration_seconds,
                    "byte_size": snapshot.byte_size,
                },
            )
    except OutputError as error:
        if (
            provider_call_completed
            and "provider_calls_attempted" not in error.details
        ):
            error._add_safe_detail("provider_calls_attempted", 1)
        raise
