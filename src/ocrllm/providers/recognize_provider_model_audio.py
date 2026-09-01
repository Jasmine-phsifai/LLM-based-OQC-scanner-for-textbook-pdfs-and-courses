"""Dispatch one scalar ProviderModel audio request through its adapter."""

from __future__ import annotations

from typing import Literal

from ..audio.probe_short_mp3 import MAX_SHORT_MP3_DURATION_SECONDS
from ..audio.snapshot_long_mp3 import LongMP3Snapshot
from ..audio.snapshot_short_mp3 import ShortMP3Snapshot
from ..audio_model_settings import AudioModelSettings
from ..config import Config
from .audio_provider_response import AudioProviderResponse
from .google_genai.recognize_short_mp3 import recognize_short_mp3
from .google_genai.recognize_uploaded_mp3 import recognize_uploaded_mp3
from .openai_compatible.provider_settings import OpenAICompatibleSettings
from .openai_compatible.recognize_openai_compatible_audio import (
    recognize_openai_compatible_audio,
)
from .provider_model import ProviderModel
from .validate_audio_provider_model import validate_audio_provider_model


def recognize_provider_model_audio(
    provider_model: ProviderModel,
    snapshot: LongMP3Snapshot,
    *,
    prompt: str,
    request_kind: Literal["whole", "interval"],
    timeout_seconds: float = 120.0,
) -> AudioProviderResponse:
    """Return one provider-neutral response without retry or fallback."""
    provider_model = validate_audio_provider_model(provider_model)
    if request_kind not in {"whole", "interval"}:
        raise ValueError("request_kind must be exactly 'whole' or 'interval'")
    if type(provider_model.settings) is OpenAICompatibleSettings:
        Config(timeout_seconds=timeout_seconds)
        return recognize_openai_compatible_audio(
            snapshot,
            prompt=prompt,
            vendor=provider_model.vendor,
            model=provider_model.model,
            settings=provider_model.settings,
            timeout_seconds=timeout_seconds,
        )

    config = Config(
        provider=provider_model.settings,
        audio_model=AudioModelSettings(name=provider_model.model),
        timeout_seconds=timeout_seconds,
    )
    if (
        request_kind == "whole"
        and snapshot.duration_seconds <= MAX_SHORT_MP3_DURATION_SECONDS
    ):
        response = recognize_short_mp3(
            ShortMP3Snapshot(
                path=snapshot.path,
                byte_size=snapshot.byte_size,
                sha256=snapshot.sha256,
                duration_seconds=snapshot.duration_seconds,
            ),
            prompt=prompt,
            config=config,
        )
        return AudioProviderResponse(
            markdown=response.markdown,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            provider_cleanup_failed=not response.client_closed,
        )

    response = recognize_uploaded_mp3(snapshot, prompt=prompt, config=config)
    return AudioProviderResponse(
        markdown=response.markdown,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        provider_cleanup_failed=(
            not response.client_closed or not response.remote_file_deleted
        ),
    )
