"""Recognize one long MP3 through a single Google Files lifecycle."""

from __future__ import annotations

import time

from ...audio.snapshot_long_mp3 import LongMP3Snapshot
from ...config import Config
from ...errors import ConfigError, OCRLLMError, ProviderError, ProviderUnavailable
from ...raise_if_cancelled import raise_if_cancelled
from ...snapshot_config import snapshot_config
from .close_google_genai_client import close_google_genai_client
from .google_client_options import google_client_options
from .google_genai_uploaded_audio_response import (
    GoogleGenAIUploadedAudioResponse,
)
from .get_google_genai_model_input_limit import (
    get_google_genai_model_input_limit,
)
from .load_google_genai import load_google_genai
from .map_google_genai_error import map_google_genai_error
from .parse_google_genai_audio_response import parse_google_genai_audio_response
from .parse_google_genai_model_catalog import parse_google_genai_model_catalog
from .provider_settings import GoogleGenAISettings
from .resolve_google_genai_credential import resolve_google_genai_credential
from .validate_google_genai_long_mp3_input_limit import (
    validate_google_genai_long_mp3_input_limit,
)


POLL_INTERVAL_SECONDS = 1.0


def recognize_uploaded_mp3(
    snapshot: LongMP3Snapshot,
    *,
    prompt: str,
    config: Config,
) -> GoogleGenAIUploadedAudioResponse:
    """Upload, await, recognize, delete, and close one owned long MP3."""
    config = snapshot_config(config)
    settings = config.provider
    if type(settings) is not GoogleGenAISettings:
        raise ConfigError(
            "Google long-audio recognition requires exact GoogleGenAISettings.",
            code="CONFIG_INVALID",
        ) from None
    model = config.audio_model.name
    if type(model) is not str or not model:
        raise ConfigError(
            "Google long-audio recognition requires an explicit model.",
            code="CONFIG_MISSING",
        ) from None

    raise_if_cancelled(config.cancellation)
    api_key: str | None = None
    client = None
    uploaded = None
    uploaded_name: str | None = None
    parsed_response = None
    public_error: OCRLLMError | None = None
    provider_calls_attempted = 0
    remote_file_deleted = False
    client_closed = False
    provider_file_cleanup_failed = False
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
            catalog_rows = tuple(client.models.list())
            served_models = parse_google_genai_model_catalog(catalog_rows)
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
                input_token_limit = get_google_genai_model_input_limit(
                    catalog_rows,
                    model=model,
                )
                validate_google_genai_long_mp3_input_limit(
                    duration_seconds=snapshot.duration_seconds,
                    input_token_limit=input_token_limit,
                    model=model,
                )
                raise_if_cancelled(config.cancellation)
                uploaded = client.files.upload(file=snapshot.path)
                uploaded_name = _remote_file_name(uploaded)
                ready_file = _wait_until_active(
                    client,
                    uploaded,
                    remote_name=uploaded_name,
                    timeout_seconds=config.timeout_seconds,
                    cancellation=config.cancellation,
                )
                raise_if_cancelled(config.cancellation)
                provider_calls_attempted = 1
                raw_response = client.models.generate_content(
                    model=model,
                    contents=[prompt, ready_file],
                )
                parsed_response = parse_google_genai_audio_response(
                    raw_response,
                    model=model,
                )
        except OCRLLMError as error:
            public_error = error
        except Exception as error:
            public_error = map_google_genai_error(error, model=model)
    finally:
        if uploaded is not None:
            if uploaded_name is None:
                provider_file_cleanup_failed = True
            else:
                try:
                    client.files.delete(name=uploaded_name)
                    remote_file_deleted = True
                except Exception:
                    provider_file_cleanup_failed = True

        close_error = close_google_genai_client(client)
        client_closed = close_error is None
        if public_error is not None:
            if provider_file_cleanup_failed:
                public_error._add_safe_detail(
                    "provider_file_cleanup_failed",
                    True,
                )
            if close_error is not None:
                public_error._add_safe_detail(
                    "provider_client_cleanup_failed",
                    True,
                )
        del api_key

    if public_error is not None:
        if "provider_calls_attempted" not in public_error.details:
            public_error._add_safe_detail(
                "provider_calls_attempted",
                provider_calls_attempted,
            )
        raise public_error from None
    if parsed_response is None:
        raise ProviderError(
            "Google GenAI returned no long-audio response.",
            code="PROVIDER_RESPONSE_INVALID",
            details={
                "provider": "google",
                "model": model,
                "provider_calls_attempted": provider_calls_attempted,
                "provider_file_cleanup_failed": provider_file_cleanup_failed,
                "provider_client_cleanup_failed": not client_closed,
            },
        ) from None
    return GoogleGenAIUploadedAudioResponse(
        markdown=parsed_response.markdown,
        input_tokens=parsed_response.input_tokens,
        output_tokens=parsed_response.output_tokens,
        remote_file_deleted=remote_file_deleted,
        client_closed=client_closed,
    )


def _wait_until_active(
    client: object,
    file_value: object,
    *,
    remote_name: str,
    timeout_seconds: float,
    cancellation: object | None,
) -> object:
    deadline = time.monotonic() + timeout_seconds
    current = file_value
    while True:
        state = _remote_file_state(current)
        if state == "ACTIVE":
            return current
        if state == "FAILED":
            raise ProviderError(
                "Google Files could not process the uploaded audio.",
                code="PROVIDER_RESPONSE_INVALID",
                details={"provider": "google", "failure_scope": "request"},
            ) from None
        if state != "PROCESSING":
            raise ProviderError(
                "Google Files returned an invalid processing state.",
                code="PROVIDER_RESPONSE_INVALID",
                details={"provider": "google", "failure_scope": "response"},
            ) from None
        raise_if_cancelled(cancellation)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProviderError(
                "Google Files processing timed out.",
                code="PROVIDER_TIMEOUT",
                details={"provider": "google", "failure_scope": "provider"},
            ) from None
        time.sleep(min(POLL_INTERVAL_SECONDS, remaining))
        raise_if_cancelled(cancellation)
        current = client.files.get(name=remote_name)


def _remote_file_name(file_value: object) -> str:
    try:
        name = getattr(file_value, "name", None)
    except Exception:
        name = None
    if type(name) is not str or not name.startswith("files/") or len(name) <= 6:
        raise ProviderError(
            "Google Files returned an invalid remote file identity.",
            code="PROVIDER_RESPONSE_INVALID",
            details={"provider": "google", "failure_scope": "response"},
        ) from None
    return name


def _remote_file_state(file_value: object) -> str:
    try:
        state = getattr(file_value, "state", None)
        name = getattr(state, "name", state)
    except Exception:
        return ""
    return name if type(name) is str else ""
