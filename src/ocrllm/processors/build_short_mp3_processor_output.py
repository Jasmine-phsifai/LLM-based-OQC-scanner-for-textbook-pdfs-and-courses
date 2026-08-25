"""Build the shared result payload for one successful inline MP3 call."""

from __future__ import annotations

from ..audio.snapshot_short_mp3 import ShortMP3Snapshot
from ..config import Config
from ..processor_output import ProcessorOutput
from ..providers.google_genai.google_genai_audio_response import (
    GoogleGenAIAudioResponse,
)


def build_short_mp3_processor_output(
    snapshot: ShortMP3Snapshot,
    response: GoogleGenAIAudioResponse,
    *,
    config: Config,
) -> ProcessorOutput:
    """Preserve inline-audio usage and client-cleanup disclosure."""
    model = config.audio_model.name
    assert type(model) is str
    warnings: tuple[str, ...] = ()
    if not response.client_closed:
        warnings = (
            "The Google GenAI client could not be closed after recognition.",
        )
    return ProcessorOutput(
        media_type="audio",
        markdown=response.markdown,
        status="partial" if warnings else "complete",
        warnings=warnings,
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
            "provider_client_closed": response.client_closed,
        },
    )
