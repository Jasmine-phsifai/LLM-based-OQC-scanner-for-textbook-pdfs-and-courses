"""Perform one synchronous DashScope vision request and parse its response."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ...config import Config
from ...errors import ConfigError, OCRLLMError, ProviderError
from ...raise_if_cancelled import raise_if_cancelled
from ...snapshot_config import snapshot_config
from .provider_settings import DashScopeSettings
from .build_dashscope_image_request import build_dashscope_image_request
from .create_dashscope_openai_client import create_dashscope_openai_client
from .credential_pool import _DashScopeCredentialLease
from .load_openai import load_openai
from .map_dashscope_error import map_dashscope_error
from .parse_dashscope_image_response import parse_dashscope_image_response
from .parse_dashscope_raw_response import parse_dashscope_raw_response
from .resolve_dashscope_credential import resolve_dashscope_credential
from .resolve_dashscope_model import resolve_dashscope_model


def recognize_images(
    image_paths: Sequence[Path],
    *,
    prompt: str,
    config: Config,
) -> str:
    """Send one ordered, no-retry request and return complete Markdown text.

    Cancellation is honored before HTTP dispatch. Once the synchronous SDK call
    starts, direct-Python cancellation cannot interrupt it.
    """
    config = snapshot_config(config)
    settings = config.provider
    if type(settings) is not DashScopeSettings:
        raise ConfigError(
            "The built-in DashScope provider requires exact DashScopeSettings.",
            code="CONFIG_INVALID",
        ) from None

    model = resolve_dashscope_model(config.vision_model.name, settings=settings)
    request = build_dashscope_image_request(
        image_paths,
        prompt=prompt,
        model=model,
        settings=settings,
        cancellation=config.cancellation,
    )
    raise_if_cancelled(config.cancellation)

    credential_lease: _DashScopeCredentialLease | None = None
    if settings.credential_pool is None:
        api_key = resolve_dashscope_credential(settings)
    else:
        credential_lease = settings.credential_pool._acquire(
            model=model,
            cancellation=config.cancellation,
        )
        api_key = credential_lease.api_key

    openai_module: object | None = None
    client: object | None = None
    markdown: str | None = None
    public_error: OCRLLMError | None = None
    try:
        try:
            openai_module = load_openai()
        except OCRLLMError as error:
            public_error = error
        except Exception:
            public_error = ProviderError(
                "The DashScope SDK could not be loaded safely.",
                code="PROVIDER_RESPONSE_INVALID",
                details={"provider": "dashscope", "model": model},
            )

        if public_error is None:
            assert openai_module is not None
            try:
                client = create_dashscope_openai_client(
                    openai_module,
                    api_key=api_key,
                    settings=settings,
                    timeout_seconds=config.timeout_seconds,
                )
            except Exception as error:
                public_error = map_dashscope_error(
                    error,
                    openai_module=openai_module,
                    model=model,
                )

        if public_error is None:
            assert openai_module is not None
            try:
                raise_if_cancelled(config.cancellation)
            except OCRLLMError as error:
                public_error = error

        if public_error is None:
            try:
                raw_response = (
                    client.chat.completions.with_raw_response.create(**request.kwargs)
                )
                completion = parse_dashscope_raw_response(raw_response, model=model)
                markdown = parse_dashscope_image_response(completion, model=model)
            except OCRLLMError as error:
                public_error = error
            except Exception as error:
                public_error = map_dashscope_error(
                    error,
                    openai_module=openai_module,
                    model=model,
                )
    finally:
        close_error = _close_client(client)
        if close_error is not None:
            if public_error is None:
                public_error = close_error
            else:
                public_error._add_safe_detail("provider_client_cleanup_failed", True)
        if credential_lease is not None:
            pool_error = (
                public_error if isinstance(public_error, ProviderError) else None
            )
            try:
                credential_lease._finish(
                    pool_error,
                    succeeded=public_error is None and markdown is not None,
                )
            except Exception:
                if public_error is None:
                    public_error = ProviderError(
                        "The DashScope credential pool could not record request state.",
                        code="PROVIDER_RESPONSE_INVALID",
                        details={"provider": "dashscope", "model": model},
                    )
                else:
                    public_error._add_safe_detail(
                        "credential_pool_update_failed",
                        True,
                    )
        del api_key

    if public_error is not None:
        raise public_error from None
    if markdown is None:  # Defensive invariant; no provider content can exist.
        raise ProviderError(
            "DashScope returned no image-recognition response.",
            code="PROVIDER_RESPONSE_INVALID",
            details={"provider": "dashscope", "model": model},
        ) from None
    return markdown


def _close_client(client: object | None) -> ProviderError | None:
    if client is None:
        return None
    try:
        close = getattr(client, "close", None)
        if not callable(close):
            raise TypeError
        close()
    except Exception:
        return ProviderError(
            "The DashScope client could not be closed safely.",
            code="PROVIDER_RESPONSE_INVALID",
            details={"provider": "dashscope"},
        )
    return None
