"""Build the shared result payload for one successful Files MP3 call."""

from __future__ import annotations

from ..audio.snapshot_long_mp3 import LongMP3Snapshot
from ..config import Config
from ..processor_output import ProcessorOutput
from ..providers.google_genai.google_genai_uploaded_audio_response import (
    GoogleGenAIUploadedAudioResponse,
)


def build_long_mp3_processor_output(
    snapshot: LongMP3Snapshot,
    response: GoogleGenAIUploadedAudioResponse,
    *,
    config: Config,
) -> ProcessorOutput:
    """Preserve Files usage plus remote and client cleanup disclosure."""
    model = config.audio_model.name
    assert type(model) is str
    warnings: list[str] = []
    if not response.remote_file_deleted:
        warnings.append(
            "The Google Files upload could not be deleted after recognition."
        )
    if not response.client_closed:
        warnings.append(
            "The Google GenAI client could not be closed after recognition."
        )
    return ProcessorOutput(
        media_type="audio",
        markdown=response.markdown,
        status="complete" if not warnings else "partial",
        warnings=tuple(warnings),
        metadata={
            "provider": "google",
            "model": model,
            "transport": "google_files",
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
            "remote_file_deleted": response.remote_file_deleted,
            "provider_client_closed": response.client_closed,
        },
    )
