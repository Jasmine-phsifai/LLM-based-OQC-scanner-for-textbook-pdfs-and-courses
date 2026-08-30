"""Perform one synchronous DashScope vision request and parse its response."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ...config import Config
from ...errors import ConfigError, OCRLLMError, ProviderError
from ...raise_if_cancelled import raise_if_cancelled
from ...snapshot_config import snapshot_config
from ..vision_provider_response import VisionProviderResponse
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
) -> str | VisionProviderResponse:
    """Send one ordered, no-retry request and return validated Markdown.

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

    model = resolve_dashscope_model(config.vision_model.name)
    raise_if_cancelled(config.cancellation)

    credential_lease: _DashScopeCredentialLease | None = None
    if settings.credential_pool is None:
        try:
            api_key = resolve_dashscope_credential(settings)
        except OCRLLMError as error:
            error._add_safe_detail("provider_calls_attempted", 0)
            raise
    else:
        try:
            credential_lease = settings.credential_pool._acquire(
                model=model,
                cancellation=config.cancellation,
            )
        except OCRLLMError as error:
            error._add_safe_detail("provider_calls_attempted", 0)
            raise
        api_key = credential_lease.api_key

    request = None
    openai_module: object | None = None
    client: object | None = None
    provider_response: VisionProviderResponse | None = None
    public_error: OCRLLMError | None = None
    client_closed = True
    try:
        try:
            model = resolve_dashscope_model(
                model,
                settings=settings,
                catalog_api_key=api_key,
            )
            raise_if_cancelled(config.cancellation)
            request = build_dashscope_image_request(
                image_paths,
                prompt=prompt,
                model=model,
                settings=settings,
                cancellation=config.cancellation,
            )
        except OCRLLMError as error:
            error._add_safe_detail("provider_calls_attempted", 0)
            public_error = error

        try:
            if public_error is None:
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
            assert request is not None
            try:
                raw_response = (
                    client.chat.completions.with_raw_response.create(**request.kwargs)
                )
                completion = parse_dashscope_raw_response(raw_response, model=model)
                provider_response = parse_dashscope_image_response(
                    completion,
                    model=model,
                )
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
        client_closed = close_error is None
        if close_error is not None:
            if public_error is not None:
                public_error._add_safe_detail("provider_client_cleanup_failed", True)
        if credential_lease is not None:
            pool_error = (
                public_error if isinstance(public_error, ProviderError) else None
            )
            try:
                credential_lease._finish(
                    pool_error,
                    succeeded=public_error is None and provider_response is not None,
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
    if provider_response is None:  # Defensive invariant; no provider content can exist.
        raise ProviderError(
            "DashScope returned no image-recognition response.",
            code="PROVIDER_RESPONSE_INVALID",
            details={"provider": "dashscope", "model": model},
        ) from None
    if client_closed:
        return provider_response
    return VisionProviderResponse(
        markdown=provider_response.markdown,
        input_tokens=provider_response.input_tokens,
        output_tokens=provider_response.output_tokens,
        client_closed=False,
    )


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
