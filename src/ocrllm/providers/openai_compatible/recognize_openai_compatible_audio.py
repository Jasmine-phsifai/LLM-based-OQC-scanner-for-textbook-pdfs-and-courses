"""Recognize one exact MP3 clip through compatible Chat Completions."""

from __future__ import annotations

from ...audio.snapshot_long_mp3 import LongMP3Snapshot
from ...errors import OCRLLMError
from ..audio_provider_response import AudioProviderResponse
from .build_openai_compatible_audio_request import (
    build_openai_compatible_audio_request,
)
from .call_openai_compatible_chat import call_openai_compatible_chat
from .parse_openai_compatible_audio_response import (
    parse_openai_compatible_audio_response,
)
from .provider_settings import OpenAICompatibleSettings


def recognize_openai_compatible_audio(
    snapshot: LongMP3Snapshot,
    *,
    prompt: str,
    vendor: str,
    model: str,
    settings: OpenAICompatibleSettings,
    timeout_seconds: float,
) -> AudioProviderResponse:
    """Return one validated transcript with no adapter-owned retry."""
    try:
        request = build_openai_compatible_audio_request(
            snapshot,
            prompt=prompt,
            model=model,
        )
    except OCRLLMError as error:
        if "provider_calls_attempted" not in error.details:
            error._add_safe_detail("provider_calls_attempted", 0)
        raise
    call = call_openai_compatible_chat(
        request.kwargs,
        vendor=vendor,
        model=model,
        settings=settings,
        timeout_seconds=timeout_seconds,
    )
    try:
        response = parse_openai_compatible_audio_response(
            call.response,
            vendor=vendor,
            model=model,
        )
    except OCRLLMError as error:
        error._add_safe_detail("provider_calls_attempted", 1)
        if not call.client_closed:
            error._add_safe_detail("provider_client_closed", False)
        raise
    if call.client_closed:
        return response
    return AudioProviderResponse(
        markdown=response.markdown,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        provider_cleanup_failed=True,
    )
