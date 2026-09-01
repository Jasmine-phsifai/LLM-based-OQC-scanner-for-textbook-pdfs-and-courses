"""Call one OpenAI-compatible Chat Completion with bounded client lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import ModuleType
from typing import Any

from ...errors import DependencyMissing, OCRLLMError, ProviderError
from .map_openai_compatible_error import map_openai_compatible_error
from .provider_settings import OpenAICompatibleSettings
from .resolve_openai_compatible_credential import (
    resolve_openai_compatible_credential,
)


@dataclass(frozen=True, slots=True)
class OpenAICompatibleChatCall:
    """Carry the raw SDK response and settled client-cleanup state."""

    response: object = field(repr=False)
    client_closed: bool = True


def call_openai_compatible_chat(
    request_kwargs: dict[str, Any],
    *,
    vendor: str,
    model: str,
    settings: OpenAICompatibleSettings,
    timeout_seconds: float,
) -> OpenAICompatibleChatCall:
    """Execute one request with no SDK retry or model fallback."""
    try:
        api_key = resolve_openai_compatible_credential(settings)
        openai_module = _load_openai()
    except OCRLLMError as error:
        if "provider_calls_attempted" not in error.details:
            error._add_safe_detail("provider_calls_attempted", 0)
        raise

    client = None
    raw_response = None
    public_error: OCRLLMError | None = None
    generation_started = False
    client_closed = True
    try:
        client = openai_module.OpenAI(
            api_key=api_key,
            base_url=settings.base_url,
            timeout=timeout_seconds,
            max_retries=0,
        )
        create = client.chat.completions.create
        if not callable(create):
            raise TypeError
        generation_started = True
        raw_response = create(**request_kwargs)
    except Exception as error:
        public_error = (
            error
            if isinstance(error, OCRLLMError)
            else map_openai_compatible_error(
                error,
                openai_module=openai_module,
                vendor=vendor,
                model=model,
            )
        )
        if "provider_calls_attempted" not in public_error.details:
            public_error._add_safe_detail(
                "provider_calls_attempted",
                1 if generation_started else 0,
            )
    finally:
        del api_key
        close_error = _close_client(client, vendor=vendor, model=model)
        if close_error is not None:
            client_closed = False
            if public_error is None and raw_response is None:
                public_error = close_error
            elif public_error is not None:
                public_error._add_safe_detail("provider_client_closed", False)

    if public_error is not None:
        raise public_error from None
    if raw_response is None:
        raise ProviderError(
            "The OpenAI-compatible endpoint returned no response boundary.",
            code="PROVIDER_RESPONSE_INVALID",
            details={
                "provider": vendor,
                "model": model,
                "provider_calls_attempted": 1 if generation_started else 0,
            },
        ) from None
    return OpenAICompatibleChatCall(
        response=raw_response,
        client_closed=client_closed,
    )


def _load_openai() -> ModuleType:
    try:
        import openai
    except (ImportError, OSError) as error:
        raise DependencyMissing(
            "OpenAI-compatible providers require the optional "
            "'openai-compatible' extra.",
            details={"extra": "openai-compatible"},
        ) from error
    version = getattr(openai, "__version__", None)
    if not _is_supported_version(version) or not callable(
        getattr(openai, "OpenAI", None)
    ):
        details = {"extra": "openai-compatible"}
        if type(version) is str and 0 < len(version) <= 64:
            details["installed_version"] = version
        raise DependencyMissing(
            "OpenAI-compatible providers require openai>=2.30,<3.",
            details=details,
        ) from None
    return openai


def _is_supported_version(value: object) -> bool:
    if type(value) is not str:
        return False
    release = value.split("+", 1)[0].split("-", 1)[0].split(".")
    return (
        len(release) >= 2
        and release[0].isdigit()
        and release[1].isdigit()
        and int(release[0]) == 2
        and int(release[1]) >= 30
    )


def _close_client(
    client: object | None,
    *,
    vendor: str,
    model: str,
) -> ProviderError | None:
    if client is None:
        return None
    try:
        close = getattr(client, "close", None)
        if not callable(close):
            raise TypeError
        close()
    except Exception:
        return ProviderError(
            "The OpenAI-compatible client could not be closed safely.",
            code="PROVIDER_RESPONSE_INVALID",
            details={"provider": vendor, "model": model},
        )
    return None
