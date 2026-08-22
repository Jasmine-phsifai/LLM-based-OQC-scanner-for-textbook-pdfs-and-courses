"""Regression tests for DashScope model-catalog cache and failure behavior."""

from __future__ import annotations

import importlib
import json

import pytest

from ocrllm.errors import ConfigError, ProviderError
from ocrllm.provider_error_disposition import get_provider_error_disposition
from ocrllm.providers.dashscope.provider_settings import DashScopeSettings


resolver = importlib.import_module(
    "ocrllm.providers.dashscope.resolve_dashscope_model"
)


class _CatalogResponse:
    def __init__(self, *model_names: str) -> None:
        self._payload = json.dumps(
            {"data": [{"id": model_name} for model_name in model_names]}
        ).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False

    def read(self, limit: int) -> bytes:
        return self._payload[:limit]


@pytest.fixture(autouse=True)
def _reset_dashscope_model_catalog_cache():
    with resolver._CATALOG_LOCK:
        resolver._CATALOG_CACHE.clear()
    yield
    with resolver._CATALOG_LOCK:
        resolver._CATALOG_CACHE.clear()


def _settings(*, api_key: str | None = "test-key") -> DashScopeSettings:
    return DashScopeSettings(
        region="cn-beijing",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=api_key,
    )


def test_failed_catalog_fetch_is_not_cached(monkeypatch) -> None:
    from urllib import request as urllib_request

    calls = 0

    def fail_then_succeed(request, *, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("temporary catalog outage")
        return _CatalogResponse("provider-model")

    monkeypatch.setattr(urllib_request, "urlopen", fail_then_succeed)

    assert resolver.fetch_dashscope_model_catalog(_settings()) is None
    assert resolver.fetch_dashscope_model_catalog(_settings()) == frozenset(
        {"provider-model"}
    )
    assert calls == 2


def test_expired_catalog_refresh_failure_serves_stale_and_retries(
    monkeypatch,
) -> None:
    from urllib import request as urllib_request

    now = [100.0]
    calls = 0

    def succeed_then_fail(request, *, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _CatalogResponse("stale-model")
        raise OSError("temporary catalog outage")

    monkeypatch.setattr(resolver, "monotonic", lambda: now[0])
    monkeypatch.setattr(urllib_request, "urlopen", succeed_then_fail)

    expected = frozenset({"stale-model"})
    assert resolver.fetch_dashscope_model_catalog(_settings()) == expected
    now[0] += resolver.DASHSCOPE_MODEL_CATALOG_CACHE_TTL_SECONDS
    assert resolver.fetch_dashscope_model_catalog(_settings()) == expected
    assert resolver.fetch_dashscope_model_catalog(_settings()) == expected
    assert calls == 3


def test_unknown_model_fails_closed_when_catalog_has_never_succeeded(
    monkeypatch,
) -> None:
    from urllib import request as urllib_request

    def raise_catalog_outage(request, *, timeout):
        raise OSError("outage")

    monkeypatch.setattr(urllib_request, "urlopen", raise_catalog_outage)

    with pytest.raises(ProviderError) as captured:
        resolver.resolve_dashscope_model("possibly-typoed-model", settings=_settings())

    assert captured.value.code == "PROVIDER_CATALOG_UNAVAILABLE"
    assert captured.value.retryable is True
    disposition = get_provider_error_disposition(captured.value)
    assert disposition.action == "retry"
    assert disposition.scope == "provider"
    assert disposition.retryable is True


def test_credential_error_propagates_without_catalog_outage_mapping(
    monkeypatch,
) -> None:
    from urllib import request as urllib_request

    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.setattr(
        urllib_request,
        "urlopen",
        lambda request, *, timeout: pytest.fail("credential failure must precede HTTP"),
    )

    with pytest.raises(ConfigError) as captured:
        resolver.fetch_dashscope_model_catalog(_settings(api_key=None))

    assert captured.value.code == "CONFIG_MISSING"


def test_pinned_baseline_model_never_fetches_catalog(monkeypatch) -> None:
    monkeypatch.setattr(
        resolver,
        "fetch_dashscope_model_catalog",
        lambda settings: pytest.fail("pinned baseline model must bypass catalog fetch"),
    )

    assert (
        resolver.resolve_dashscope_model(
            resolver.DEFAULT_DASHSCOPE_MODEL,
            settings=_settings(),
        )
        == resolver.DEFAULT_DASHSCOPE_MODEL
    )


@pytest.mark.parametrize("model", ["qwen3.7-plus", "qwen-vl-max"])
def test_unpinned_models_are_validated_against_the_catalog(monkeypatch, model) -> None:
    monkeypatch.setattr(
        resolver,
        "fetch_dashscope_model_catalog",
        lambda settings: frozenset({model}),
    )
    assert resolver.resolve_dashscope_model(model, settings=_settings()) == model

    monkeypatch.setattr(
        resolver,
        "fetch_dashscope_model_catalog",
        lambda settings: frozenset(),
    )
    with pytest.raises(ConfigError, match="DashScope does not serve"):
        resolver.resolve_dashscope_model(model, settings=_settings())
