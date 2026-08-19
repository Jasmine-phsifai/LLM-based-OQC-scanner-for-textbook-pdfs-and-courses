"""Resolve the explicit or reproducibly pinned DashScope vision model."""

from __future__ import annotations

import json
from threading import Lock

from ...errors import ConfigError


DEFAULT_DASHSCOPE_MODEL = "qwen3.7-plus-2026-05-26"
SUPPORTED_DASHSCOPE_MODELS = frozenset(
    {"qwen3.7-plus", DEFAULT_DASHSCOPE_MODEL, "qwen-vl-max"}
)
_CATALOG_CACHE: dict[str, frozenset[str] | None] = {}
_CATALOG_LOCK = Lock()


def resolve_dashscope_model(configured_model: str | None, *, settings=None) -> str:
    """Return the caller's model, checking the provider catalog when available."""
    if configured_model is not None and type(configured_model) is not str:
        raise ConfigError(
            "Config.model must be an exact string for the DashScope adapter.",
            code="CONFIG_INVALID",
        ) from None
    model = DEFAULT_DASHSCOPE_MODEL if configured_model is None else configured_model
    if settings is not None and model not in SUPPORTED_DASHSCOPE_MODELS:
        catalog = fetch_dashscope_model_catalog(settings)
        if catalog is not None and model not in catalog:
            raise ConfigError(
                "DashScope does not serve the requested model according to its "
                "provider model catalog.",
                code="CONFIG_INVALID",
            ) from None
    return model


def fetch_dashscope_model_catalog(settings) -> frozenset[str] | None:
    """Fetch and process-cache the provider catalog; outages fail open."""
    cache_key = settings.base_url
    with _CATALOG_LOCK:
        if cache_key in _CATALOG_CACHE:
            return _CATALOG_CACHE[cache_key]
    try:
        from urllib.request import Request, urlopen
        from .resolve_dashscope_credential import resolve_dashscope_credential

        api_key = settings.api_key or resolve_dashscope_credential(settings)
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
        catalog = names or None
    except Exception:
        catalog = None
    with _CATALOG_LOCK:
        _CATALOG_CACHE[cache_key] = catalog
    return catalog
