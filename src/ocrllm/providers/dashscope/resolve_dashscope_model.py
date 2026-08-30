"""Resolve the explicit or reproducibly pinned DashScope vision model."""

from __future__ import annotations

import json
from threading import Lock
from time import monotonic

from ...errors import ConfigError, ProviderError


DEFAULT_DASHSCOPE_MODEL = "qwen3.7-plus-2026-05-26"
DASHSCOPE_MODEL_CATALOG_CACHE_TTL_SECONDS = 600
_CATALOG_CACHE: dict[str, tuple[frozenset[str], float]] = {}
_CATALOG_LOCK = Lock()


def resolve_dashscope_model(
    configured_model: str | None,
    *,
    settings=None,
    catalog_api_key: str | None = None,
) -> str:
    """Return the caller's model, checking the provider catalog when available."""
    if configured_model is not None and type(configured_model) is not str:
        raise ConfigError(
            "Config.model must be an exact string for the DashScope adapter.",
            code="CONFIG_INVALID",
        ) from None
    model = DEFAULT_DASHSCOPE_MODEL if configured_model is None else configured_model
    # The pinned default is proven by the Phase 1 v17 live gate, so it needs no
    # catalog row. Every other model is validated against the live catalog:
    # unknown means "the provider does not serve this", never "this repository
    # has not heard of it".
    if settings is not None and model != DEFAULT_DASHSCOPE_MODEL:
        catalog = (
            fetch_dashscope_model_catalog(settings)
            if catalog_api_key is None
            else fetch_dashscope_model_catalog(
                settings,
                catalog_api_key=catalog_api_key,
            )
        )
        if catalog is None:
            raise ProviderError(
                "The DashScope model catalog is temporarily unavailable.",
                code="PROVIDER_CATALOG_UNAVAILABLE",
                retryable=True,
                details={"provider": "dashscope", "model": model},
            ) from None
        if model not in catalog:
            raise ConfigError(
                "DashScope does not serve the requested model according to its "
                "provider model catalog.",
                code="CONFIG_INVALID",
            ) from None
    return model


def fetch_dashscope_model_catalog(
    settings,
    *,
    catalog_api_key: str | None = None,
) -> frozenset[str]:
    """Return a fresh catalog or a stale success; otherwise raise safely."""
    cache_key = settings.base_url
    now = monotonic()
    with _CATALOG_LOCK:
        cached = _CATALOG_CACHE.get(cache_key)
        if (
            cached is not None
            and now - cached[1] < DASHSCOPE_MODEL_CATALOG_CACHE_TTL_SECONDS
        ):
            return cached[0]

    from urllib.request import Request, urlopen
    from .resolve_dashscope_credential import resolve_dashscope_credential
    from .validate_dashscope_api_key import validate_dashscope_api_key

    api_key = (
        resolve_dashscope_credential(settings)
        if catalog_api_key is None
        else validate_dashscope_api_key(
            catalog_api_key,
            field_name="leased DashScope catalog credential",
        )
    )
    try:
        request = Request(
            f"{settings.base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            method="GET",
        )
        with urlopen(request, timeout=5.0) as response:
            payload = json.loads(response.read(2_000_000).decode("utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ValueError("DashScope returned a malformed model catalog.")
        model_names: list[str] = []
        for row in payload["data"]:
            if not isinstance(row, dict):
                raise ValueError("DashScope returned a malformed model catalog row.")
            model_name = row.get("id")
            if not isinstance(model_name, str) or not model_name:
                raise ValueError("DashScope returned a model row without an id.")
            model_names.append(model_name)
        names = frozenset(model_names)
        if not names:
            raise ValueError("DashScope returned an empty model catalog.")
    except Exception as error:
        with _CATALOG_LOCK:
            latest_cached = _CATALOG_CACHE.get(cache_key)
        if latest_cached is not None:
            return latest_cached[0]
        if isinstance(error, ValueError):
            public_error = ProviderError(
                "DashScope returned a malformed model catalog.",
                code="PROVIDER_RESPONSE_INVALID",
                details={
                    "provider": "dashscope",
                    "failure_scope": "provider",
                    "reason": "catalog_malformed",
                },
            )
        else:
            from .map_dashscope_error import map_dashscope_error

            public_error = map_dashscope_error(
                error,
                openai_module=None,
                model=None,
            )
        public_error._add_safe_detail("provider_operation", "catalog")
        public_error._add_safe_detail("provider_calls_attempted", 0)
        raise public_error from None

    with _CATALOG_LOCK:
        _CATALOG_CACHE[cache_key] = (names, monotonic())
    return names
