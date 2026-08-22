"""Call one resolved vision provider and validate one Markdown response."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ..config import Config
from ..errors import ConfigError, OCRLLMError, ProviderError
from .bounded_provider_call import BoundedProviderCall, ProviderDeadlineExceeded
from .map_injected_provider_error import map_injected_provider_error
from .provider_request_start_gate import wait_for_provider_request_start
from .resolved_vision_provider import ResolvedVisionProvider
from .validate_provider_markdown import validate_provider_markdown


def call_vision_provider(
    resolved_provider: ResolvedVisionProvider,
    image_paths: Sequence[Path],
    *,
    prompt: str,
    config: Config,
) -> str:
    """Return one complete provider response or one redacted typed failure."""

    provider = resolved_provider.value
    try:
        recognize_method = getattr(provider, "recognize_images", None)
    except Exception:
        del provider
        raise ConfigError(
            "Config.provider recognize_images could not be inspected safely.",
            code="CONFIG_INVALID",
        ) from None
    if not callable(recognize_method):
        del provider, recognize_method
        raise ConfigError(
            "Config.provider must be an injected object with a callable recognize_images method.",
            code="CONFIG_INVALID",
        )

    dispatch_error: OCRLLMError | None = None
    try:
        provider_value = _dispatch_provider_call(
            recognize_method,
            image_paths,
            prompt=prompt,
            config=config,
            resolved_provider=resolved_provider,
        )
    except ProviderDeadlineExceeded:
        del provider, recognize_method
        raise ProviderError(
            "The configured provider did not respond within Config.timeout_seconds.",
            code="PROVIDER_TIMEOUT",
            retryable=True,
            details={
                **_known_provider_details(resolved_provider),
                "timeout_seconds": config.timeout_seconds,
                # The blocked call cannot be interrupted; its worker thread is
                # abandoned as a daemon rather than joined.
                "abandoned_provider_thread": True,
            },
        ) from None
    except Exception as error:
        if resolved_provider.built_in and isinstance(error, OCRLLMError):
            dispatch_error = error
        else:
            dispatch_error = map_injected_provider_error(
                error,
                model=resolved_provider.model,
            )
    if dispatch_error is not None:
        del provider, recognize_method
        raise dispatch_error

    validation_error: ProviderError | None = None
    try:
        markdown = validate_provider_markdown(provider_value)
    except ProviderError as error:
        validation_error = ProviderError(
            str(error),
            code=error.code,
            details={
                **dict(error.details),
                **_known_provider_details(resolved_provider),
            },
        )
    if validation_error is not None:
        del provider, recognize_method, provider_value
        raise validation_error
    return markdown


def _known_provider_details(
    resolved_provider: ResolvedVisionProvider,
) -> dict[str, str]:
    return {
        key: value
        for key, value in (
            ("model", resolved_provider.model),
            ("provider", resolved_provider.name),
        )
        if value is not None
    }


def _dispatch_provider_call(
    recognize_method: object,
    image_paths: Sequence[Path],
    *,
    prompt: str,
    config: Config,
    resolved_provider: ResolvedVisionProvider,
) -> object:
    """Pace the request, then bound injected providers that have no transport timeout."""
    assert callable(recognize_method)
    if resolved_provider.built_in:
        wait_for_provider_request_start(config.cancellation)
        return recognize_method(tuple(image_paths), prompt=prompt, config=config)
    with BoundedProviderCall(
        lambda: recognize_method(tuple(image_paths), prompt=prompt, config=config)
    ) as bounded_call:
        wait_for_provider_request_start(config.cancellation)
        return bounded_call.run_within(config.timeout_seconds)
