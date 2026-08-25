"""Perform one native Google GenAI inline short-MP3 request."""

from __future__ import annotations

from dataclasses import replace

from ...audio.snapshot_short_mp3 import ShortMP3Snapshot
from ...config import Config
from ...errors import ConfigError, OCRLLMError, ProviderError, ProviderUnavailable
from ...raise_if_cancelled import raise_if_cancelled
from ...snapshot_config import snapshot_config
from .build_google_genai_audio_request import build_google_genai_audio_request
from .close_google_genai_client import close_google_genai_client
from .google_client_options import google_client_options
from .google_genai_audio_response import GoogleGenAIAudioResponse
from .load_google_genai import load_google_genai
from .map_google_genai_error import map_google_genai_error
from .parse_google_genai_audio_response import parse_google_genai_audio_response
from .parse_google_genai_model_catalog import parse_google_genai_model_catalog
from .provider_settings import GoogleGenAISettings
from .resolve_google_genai_credential import resolve_google_genai_credential


def recognize_short_mp3(
    snapshot: ShortMP3Snapshot,
    *,
    prompt: str,
    config: Config,
) -> GoogleGenAIAudioResponse:
    """Preflight, discover, and dispatch exactly one inline audio call."""
    config = snapshot_config(config)
    settings = config.provider
    if type(settings) is not GoogleGenAISettings:
        raise ConfigError(
            "Google short-audio recognition requires exact GoogleGenAISettings.",
            code="CONFIG_INVALID",
        ) from None
    model = config.audio_model.name
    if type(model) is not str or not model:
        raise ConfigError(
            "Google short-audio recognition requires an explicit model.",
            code="CONFIG_MISSING",
        ) from None

    request = build_google_genai_audio_request(
        snapshot.path,
        prompt=prompt,
        model=model,
        cancellation=config.cancellation,
    )
    raise_if_cancelled(config.cancellation)
    api_key: str | None = None
    client = None
    response: GoogleGenAIAudioResponse | None = None
    public_error: OCRLLMError | None = None
    provider_calls_attempted = 0
    client_closed = True
    try:
        try:
            google_module = load_google_genai()
            api_key = resolve_google_genai_credential(settings)
            client = google_module.Client(
                api_key=api_key,
                http_options=google_client_options(
                    google_module,
                    timeout_seconds=config.timeout_seconds,
                ),
            )
            served_models = parse_google_genai_model_catalog(client.models.list())
            if model not in served_models:
                public_error = ProviderUnavailable(
                    "The selected Google GenAI model is not currently served.",
                    details={
                        "provider": "google",
                        "model": model,
                        "failure_scope": "model",
                    },
                )
            else:
                raise_if_cancelled(config.cancellation)
                sdk_contents = _sdk_contents(google_module, request.contents)
                provider_calls_attempted = 1
                raw_response = client.models.generate_content(
                    model=model,
                    contents=sdk_contents,
                )
                response = parse_google_genai_audio_response(raw_response, model=model)
        except OCRLLMError as error:
            public_error = error
        except Exception as error:
            public_error = map_google_genai_error(error, model=model)
    finally:
        close_error = close_google_genai_client(client)
        client_closed = close_error is None
        if close_error is not None:
            if public_error is not None:
                public_error._add_safe_detail("provider_client_cleanup_failed", True)
        del api_key

    if public_error is not None:
        if "provider_calls_attempted" not in public_error.details:
            public_error._add_safe_detail(
                "provider_calls_attempted", provider_calls_attempted
            )
        raise public_error from None
    if response is None:
        raise ProviderError(
            "Google GenAI returned no short-audio response.",
            code="PROVIDER_RESPONSE_INVALID",
            details={
                "provider": "google",
                "model": model,
                "provider_calls_attempted": provider_calls_attempted,
                "provider_client_cleanup_failed": not client_closed,
            },
        ) from None
    return replace(response, client_closed=client_closed)


def _sdk_contents(google_module: object, contents: tuple[object, ...]) -> list[object]:
    sdk_contents: list[object] = []
    for content in contents:
        if type(content) is str:
            sdk_contents.append(content)
        else:
            sdk_contents.append(
                google_module.types.Part.from_bytes(
                    data=content.data,
                    mime_type=content.mime_type,
                )
            )
    return sdk_contents
