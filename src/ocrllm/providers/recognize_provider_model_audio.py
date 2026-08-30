"""Run one scalar provider model through the Google Files audio boundary."""

from __future__ import annotations

from typing import Literal

from ..audio.snapshot_short_mp3 import ShortMP3Snapshot
from ..audio.snapshot_long_mp3 import LongMP3Snapshot
from ..audio_model_settings import AudioModelSettings
from ..config import Config
from .google_genai.google_genai_uploaded_audio_response import (
    GoogleGenAIUploadedAudioResponse,
)
from .google_genai.google_genai_audio_response import GoogleGenAIAudioResponse
from .google_genai.recognize_short_mp3 import recognize_short_mp3
from .google_genai.recognize_uploaded_mp3 import recognize_uploaded_mp3
from .provider_model import ProviderModel
from .validate_audio_provider_model import validate_audio_provider_model


def recognize_provider_model_audio(
    provider_model: ProviderModel,
    snapshot: LongMP3Snapshot,
    *,
    prompt: str,
    transport: Literal["inline", "files"],
    timeout_seconds: float = 120.0,
) -> GoogleGenAIAudioResponse | GoogleGenAIUploadedAudioResponse:
    """Dispatch one no-fallback audio request through its admitted adapter."""
    provider_model = validate_audio_provider_model(provider_model)
    config = Config(
        provider=provider_model.settings,
        audio_model=AudioModelSettings(name=provider_model.model),
        timeout_seconds=timeout_seconds,
    )
    if transport == "inline":
        return recognize_short_mp3(
            ShortMP3Snapshot(
                path=snapshot.path,
                byte_size=snapshot.byte_size,
                sha256=snapshot.sha256,
                duration_seconds=snapshot.duration_seconds,
            ),
            prompt=prompt,
            config=config,
        )
    if transport == "files":
        return recognize_uploaded_mp3(snapshot, prompt=prompt, config=config)
    raise ValueError("transport must be exactly 'inline' or 'files'")
