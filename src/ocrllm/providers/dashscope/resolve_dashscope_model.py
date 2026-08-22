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


def resolve_dashscope_model(configured_model: str | None, *, settings=None) -> str:
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
        catalog = fetch_dashscope_model_catalog(settings)
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


def fetch_dashscope_model_catalog(settings) -> frozenset[str] | None:
    """Return a fresh catalog, or the last success during a refresh outage."""
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

    api_key = resolve_dashscope_credential(settings)
    try:
        request = Request(
            f"{settings.base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            method="GET",
        )
        with urlopen(request, timeout=5.0) as response:
            payload = json.loads(response.read(2_000_000).decode("utf-8"))
        rows = payload.get("data", payload) if isinstance(payload, dict) else payload
        names = frozenset(
            row.get("id")
            for row in rows
            if isinstance(row, dict) and isinstance(row.get("id"), str)
        )
    except Exception:
        with _CATALOG_LOCK:
            latest_cached = _CATALOG_CACHE.get(cache_key)
        return latest_cached[0] if latest_cached is not None else None

    if not names:
        with _CATALOG_LOCK:
            latest_cached = _CATALOG_CACHE.get(cache_key)
        return latest_cached[0] if latest_cached is not None else None
    with _CATALOG_LOCK:
        _CATALOG_CACHE[cache_key] = (names, monotonic())
    return names
