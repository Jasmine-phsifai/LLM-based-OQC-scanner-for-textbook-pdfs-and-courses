"""List current native Google generateContent model identifiers."""

from __future__ import annotations

import math

from ...errors import ConfigError, OCRLLMError
from .close_google_genai_client import close_google_genai_client
from .google_client_options import google_client_options
from .load_google_genai import load_google_genai
from .map_google_genai_error import map_google_genai_error
from .parse_google_genai_model_catalog import parse_google_genai_model_catalog
from .provider_settings import GoogleGenAISettings
from .resolve_google_genai_credential import resolve_google_genai_credential


def list_google_genai_models(
    settings: GoogleGenAISettings,
    timeout_seconds: float = 30.0,
) -> tuple[str, ...]:
    """Fetch canonical current model IDs without caching or hardcoding."""
    if type(settings) is not GoogleGenAISettings:
        raise ConfigError(
            "Google model discovery requires exact GoogleGenAISettings.",
            code="CONFIG_INVALID",
        ) from None
    timeout = _validate_timeout(timeout_seconds)
    google_module = load_google_genai()
    api_key = resolve_google_genai_credential(settings)
    client = None
    public_error: OCRLLMError | None = None
    models: tuple[str, ...] | None = None
    provider_operation = "client_setup"
    try:
        try:
            client = google_module.Client(
                api_key=api_key,
                http_options=google_client_options(
                    google_module,
                    timeout_seconds=timeout,
                ),
            )
            provider_operation = "catalog"
            models = parse_google_genai_model_catalog(client.models.list())
        except OCRLLMError as error:
            public_error = error
        except Exception as error:
            public_error = map_google_genai_error(error, model="catalog")
    finally:
        close_error = close_google_genai_client(client)
        if close_error is not None:
            if public_error is None:
                public_error = close_error
                provider_operation = "cleanup"
            else:
                public_error._add_safe_detail("provider_client_cleanup_failed", True)
        del api_key
    if public_error is not None:
        public_error._add_safe_detail("provider_operation", provider_operation)
        raise public_error from None
    return () if models is None else models


def _validate_timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError("timeout_seconds must be a finite positive number.") from None
    timeout = float(value)
    if not math.isfinite(timeout) or not 0 < timeout <= 600:
        raise ConfigError("timeout_seconds must be in the interval (0, 600].") from None
    return timeout
