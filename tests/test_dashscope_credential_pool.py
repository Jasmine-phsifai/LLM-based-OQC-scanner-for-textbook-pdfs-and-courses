from __future__ import annotations

import importlib
import json
import threading
import time
from types import SimpleNamespace

import pytest

from ocrllm import (
    Cancelled,
    ConcurrencyLimited,
    Config,
    CredentialPoolPolicy,
    DashScopeCredential,
    DashScopeCredentialPool,
    DashScopeSettings,
    ProviderAccountSuspended,
    ProviderError,
    ProviderPermissionDenied,
    RateLimited,
    VisionModelSettings,
    recognize,
)
from ocrllm.errors import ConfigError, QuotaExhausted
from ocrllm.providers.dashscope.map_dashscope_error import map_dashscope_error

from write_test_image import write_test_image


MODEL = "qwen3.7-plus-2026-05-26"


def _credential(index: int) -> DashScopeCredential:
    return DashScopeCredential(
        credential_id=f"credential-{index}",
        api_key=f"pool-secret-key-{index}",
    )


def _pool(
    count: int = 2,
    *,
    policy: CredentialPoolPolicy | None = None,
) -> DashScopeCredentialPool:
    return DashScopeCredentialPool(
        region="cn-beijing",
        credentials=tuple(_credential(index) for index in range(count)),
        policy=policy,
    )


def _selected_id(pool: DashScopeCredentialPool) -> str:
    selected = [slot.credential_id for slot in pool.snapshot().slots if slot.in_flight]
    assert len(selected) == 1
    return selected[0]


def test_credential_and_policy_are_frozen_bounded_and_secret_safe() -> None:
    credential = _credential(0)
    policy = CredentialPoolPolicy(
        max_in_flight_per_credential=2,
        cooldown_seconds=1,
        selection_timeout_seconds=2,
    )

    assert credential.credential_id == "credential-0"
    assert "pool-secret-key-0" not in repr(credential)
    assert policy.cooldown_seconds == 1.0
    assert policy.selection_timeout_seconds == 2.0

    for bad_id in ("", "spaces are unsafe", "x" * 65, 1, True):
        with pytest.raises(ConfigError, match="credential_id"):
            DashScopeCredential(
                credential_id=bad_id,  # type: ignore[arg-type]
                api_key="safe-key",
            )
    for bad_key in ("", " padded ", "sk-sp-coding-plan", 1, True):
        with pytest.raises(ConfigError) as captured:
            DashScopeCredential(
                credential_id="safe-id",
                api_key=bad_key,  # type: ignore[arg-type]
            )
        if bad_key:
            assert str(bad_key) not in str(captured.value)

    for field_name, bad_value in (
        ("max_in_flight_per_credential", 0),
        ("max_in_flight_per_credential", 33),
        ("cooldown_seconds", -1),
        ("cooldown_seconds", 601),
        ("selection_timeout_seconds", 0),
        ("selection_timeout_seconds", 601),
    ):
        with pytest.raises(ConfigError, match=field_name):
            CredentialPoolPolicy(**{field_name: bad_value})


def test_pool_rejects_duplicate_or_ambiguous_credentials_without_echo() -> None:
    first = _credential(0)
    duplicate_id = DashScopeCredential(
        credential_id=first.credential_id,
        api_key="another-secret",
    )
    duplicate_key = DashScopeCredential(
        credential_id="another-id",
        api_key=first.api_key,
    )

    for credentials in ((first, duplicate_id), (first, duplicate_key)):
        with pytest.raises(ConfigError) as captured:
            DashScopeCredentialPool(region="cn-beijing", credentials=credentials)
        assert first.api_key not in str(captured.value)
        assert "another-secret" not in str(captured.value)

    with pytest.raises(ConfigError, match="1-64"):
        DashScopeCredentialPool(region="cn-beijing", credentials=())
    with pytest.raises(ConfigError, match="supported canonical region"):
        DashScopeCredentialPool(region="unknown", credentials=(first,))
    with pytest.raises(ConfigError, match="exact DashScopeCredential"):
        DashScopeCredentialPool(
            region="cn-beijing",
            credentials=(object(),),  # type: ignore[arg-type]
        )


def test_settings_compose_one_region_matched_pool_without_copying_state() -> None:
    pool = _pool()
    settings = DashScopeSettings(
        region="cn-beijing",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        credential_pool=pool,
    )
    config = Config(provider=settings)

    assert type(config.provider) is DashScopeSettings
    assert config.provider.credential_pool is pool
    assert "pool-secret-key" not in repr(settings)
    assert "pool-secret-key" not in repr(config)

    with pytest.raises(ConfigError, match="mutually exclusive"):
        DashScopeSettings(
            region="cn-beijing",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key="single-key",
            credential_pool=pool,
        )
    with pytest.raises(ConfigError, match="regions must match"):
        DashScopeSettings(
            region="ap-southeast-1",
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            credential_pool=pool,
        )


def test_serial_selection_rotates_fairly_instead_of_restarting_at_first() -> None:
    pool = _pool(3)
    selected = []

    for _ in range(4):
        lease = pool._acquire(model=MODEL, cancellation=None)
        selected.append(_selected_id(pool))
        lease._finish(None, succeeded=True)

    assert selected == [
        "credential-0",
        "credential-1",
        "credential-2",
        "credential-0",
    ]
    reports = pool.snapshot().slots
    assert [slot.selection_count for slot in reports] == [2, 1, 1]
    assert [slot.success_count for slot in reports] == [2, 1, 1]


def test_concurrent_leases_balance_and_enforce_per_credential_cap() -> None:
    pool = _pool(2)
    first = pool._acquire(model=MODEL, cancellation=None)
    second = pool._acquire(model=MODEL, cancellation=None)

    assert [slot.in_flight for slot in pool.snapshot().slots] == [1, 1]

    acquired = threading.Event()
    release = threading.Event()
    thread_error: list[BaseException] = []

    def acquire_third() -> None:
        try:
            third = pool._acquire(model=MODEL, cancellation=None)
            acquired.set()
            release.wait(timeout=5)
            third._finish(None, succeeded=True)
        except BaseException as error:
            thread_error.append(error)

    thread = threading.Thread(target=acquire_third)
    thread.start()
    assert not acquired.wait(timeout=0.05)
    first._finish(None, succeeded=True)
    assert acquired.wait(timeout=2)
    release.set()
    second._finish(None, succeeded=True)
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert thread_error == []
    assert max(slot.in_flight for slot in pool.snapshot().slots) == 0


def test_capacity_wait_is_cancellable_and_bounded() -> None:
    pool = _pool(
        1,
        policy=CredentialPoolPolicy(selection_timeout_seconds=0.05),
    )
    lease = pool._acquire(model=MODEL, cancellation=None)

    with pytest.raises(ConcurrencyLimited) as timed_out:
        pool._acquire(model=MODEL, cancellation=None)
    assert timed_out.value.details["pool_state"] == "capacity_wait_timeout"

    cancellation = threading.Event()
    cancellation.set()
    with pytest.raises(Cancelled):
        pool._acquire(model=MODEL, cancellation=cancellation)

    lease._finish(None, succeeded=False)


def test_authentication_quarantines_only_one_slot_and_restore_is_explicit() -> None:
    pool = _pool(2)
    first = pool._acquire(model=MODEL, cancellation=None)
    first._finish(
        ProviderError(
            code="PROVIDER_AUTHENTICATION",
            details={"failure_scope": "credential"},
        ),
        succeeded=False,
    )

    reports = pool.snapshot().slots
    assert reports[0].state == "quarantined"
    assert reports[0].last_error_code == "PROVIDER_AUTHENTICATION"
    second = pool._acquire(model=MODEL, cancellation=None)
    assert _selected_id(pool) == "credential-1"
    second._finish(None, succeeded=True)

    pool.restore_credential("credential-0")
    assert pool.snapshot().slots[0].state == "available"


def test_model_and_account_blocks_require_explicit_external_recovery() -> None:
    pool = _pool(2)
    model_lease = pool._acquire(model=MODEL, cancellation=None)
    model_lease._finish(
        ProviderPermissionDenied(details={"failure_scope": "model"}),
        succeeded=False,
    )

    with pytest.raises(ProviderPermissionDenied) as model_blocked:
        pool._acquire(model=MODEL, cancellation=None)
    assert model_blocked.value.details["failure_scope"] == "model"
    other = pool._acquire(model="qwen-vl-max", cancellation=None)
    other._finish(None, succeeded=True)
    pool.clear_model_block(MODEL)

    account_lease = pool._acquire(model=MODEL, cancellation=None)
    account_lease._finish(
        ProviderAccountSuspended(details={"failure_scope": "account"}),
        succeeded=False,
    )
    assert pool.snapshot().account_state == "blocked"
    with pytest.raises(ProviderAccountSuspended):
        pool._acquire(model="qwen-vl-max", cancellation=None)
    pool.clear_account_block()
    recovered = pool._acquire(model=MODEL, cancellation=None)
    recovered._finish(None, succeeded=True)


def test_cooldown_changes_later_selection_but_never_retries_same_lease() -> None:
    pool = _pool(
        2,
        policy=CredentialPoolPolicy(cooldown_seconds=0.05),
    )
    lease = pool._acquire(model=MODEL, cancellation=None)
    lease._finish(
        ConcurrencyLimited(details={"failure_scope": "credential"}),
        succeeded=False,
    )

    report = pool.snapshot()
    assert report.slots[0].state == "cooldown"
    assert report.slots[0].failure_count == 1
    next_lease = pool._acquire(model=MODEL, cancellation=None)
    assert _selected_id(pool) == "credential-1"
    next_lease._finish(None, succeeded=True)


@pytest.mark.parametrize("failure_scope", ["model", "account", "provider"])
def test_shared_cooldowns_wait_then_recover_without_switching_inside_call(
    failure_scope: str,
) -> None:
    pool = _pool(
        2,
        policy=CredentialPoolPolicy(
            cooldown_seconds=0.05,
            selection_timeout_seconds=1,
        ),
    )
    failed = pool._acquire(model=MODEL, cancellation=None)
    failed._finish(
        ConcurrencyLimited(details={"failure_scope": failure_scope}),
        succeeded=False,
    )

    report = pool.snapshot()
    if failure_scope == "model":
        assert dict(report.model_cooldowns)[MODEL] > 0
        unrelated = pool._acquire(model="qwen-vl-max", cancellation=None)
        unrelated._finish(None, succeeded=True)
    else:
        assert report.account_state == "cooldown"

    started = time.monotonic()
    recovered = pool._acquire(model=MODEL, cancellation=None)
    elapsed = time.monotonic() - started
    recovered._finish(None, succeeded=True)

    assert elapsed >= 0.01
    assert pool.snapshot().account_state == "available"


def test_free_tier_exhaustion_blocks_only_that_model() -> None:
    pool = _pool(1)
    raw = RuntimeError("raw provider body")
    raw.status_code = 403
    raw.body = {"code": "AllocationQuota.FreeTierOnly"}
    mapped = map_dashscope_error(raw, openai_module=_FakeOpenAI, model="free-model")

    lease = pool._acquire(model="free-model", cancellation=None)
    lease._finish(mapped, succeeded=False)

    report = pool.snapshot()
    assert report.account_state == "available"
    assert dict(report.model_blocks) == {"free-model": "PROVIDER_QUOTA_EXHAUSTED"}

    other = pool._acquire(model="other-model", cancellation=None)
    other._finish(None, succeeded=True)
    with pytest.raises(QuotaExhausted):
        pool._acquire(model="free-model", cancellation=None)


def test_account_suspension_still_blocks_every_model() -> None:
    pool = _pool(1)
    raw = RuntimeError("raw provider body")
    raw.status_code = 403
    raw.body = {"code": "AccountSuspended"}
    mapped = map_dashscope_error(raw, openai_module=_FakeOpenAI, model=MODEL)

    lease = pool._acquire(model=MODEL, cancellation=None)
    lease._finish(mapped, succeeded=False)

    assert pool.snapshot().account_state == "blocked"
    with pytest.raises(ProviderAccountSuspended):
        pool._acquire(model="other-model", cancellation=None)


def test_snapshot_is_immutable_ordered_and_contains_no_keys() -> None:
    pool = _pool(2)

    report = pool.snapshot()
    rendered = repr(report)

    assert report.region == "cn-beijing"
    assert report.account_state == "available"
    assert [slot.credential_id for slot in report.slots] == [
        "credential-0",
        "credential-1",
    ]
    assert "pool-secret-key-0" not in rendered
    assert "pool-secret-key-1" not in rendered


class _FakeClient:
    def __init__(self, state: SimpleNamespace) -> None:
        self.state = state
        self.chat = self
        self.completions = self
        self.with_raw_response = self

    def create(self, **kwargs):
        self.state.calls.append(kwargs)
        call_index = len(self.state.calls)
        if self.state.fail_first and call_index == 1:
            error = self.state.module.RateLimitError("private throttle")
            error.status_code = 429
            error.body = {"code": "Throttling.RateQuota"}
            raise error
        content = "# Pooled board\n" if call_index == 1 else "NONE"
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    index=0,
                    finish_reason="stop",
                    message=SimpleNamespace(
                        role="assistant",
                        refusal=None,
                        content=content,
                    ),
                )
            ],
            model=kwargs["model"],
        )
        return SimpleNamespace(headers={}, parse=lambda: response)

    def close(self) -> None:
        return None


class _FakeOpenAI:
    class APITimeoutError(Exception):
        pass

    class APIConnectionError(Exception):
        pass

    class AuthenticationError(Exception):
        pass

    class PermissionDeniedError(Exception):
        pass

    class RateLimitError(Exception):
        pass

    class InternalServerError(Exception):
        pass

    def __init__(self, *, fail_first: bool = False) -> None:
        self.state = SimpleNamespace(
            calls=[],
            keys=[],
            fail_first=fail_first,
            module=self,
        )

    def OpenAI(self, **kwargs):
        self.state.keys.append(kwargs["api_key"])
        return _FakeClient(self.state)


class _CatalogResponse:
    def __init__(self, model: str) -> None:
        self._payload = json.dumps({"data": [{"id": model}]}).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False

    def read(self, limit: int) -> bytes:
        return self._payload[:limit]


def _pooled_config(pool: DashScopeCredentialPool, *, scout: bool = False) -> Config:
    return Config(
        provider=DashScopeSettings(
            region="cn-beijing",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            credential_pool=pool,
            enable_thinking=True,
            standalone_sign_scout_model="qwen-vl-max" if scout else None,
        )
    )


def _explicit_pooled_config(
    pool: DashScopeCredentialPool,
    *,
    workspace: str,
    cancellation: object | None = None,
) -> Config:
    return Config(
        provider=DashScopeSettings(
            region="cn-beijing",
            base_url=(
                f"https://{workspace}.cn-beijing.maas.aliyuncs.com"
                "/compatible-mode/v1"
            ),
            credential_pool=pool,
        ),
        vision_model=VisionModelSettings(name="qwen-vl-max"),
        cancellation=cancellation,
    )


def test_public_explicit_model_uses_one_pool_lease_for_catalog_and_recognition(
    tmp_path,
    monkeypatch,
) -> None:
    from urllib import request as urllib_request

    source = write_test_image(tmp_path / "board.png", size=(12, 13))
    pool = _pool(1)
    fake_openai = _FakeOpenAI()
    adapter = importlib.import_module("ocrllm.providers.dashscope.recognize_images")
    monkeypatch.setattr(adapter, "load_openai", lambda: fake_openai)
    catalog_keys: list[str] = []

    def return_catalog(request, *, timeout):
        catalog_keys.append(request.get_header("Authorization"))
        return _CatalogResponse("qwen-vl-max")

    monkeypatch.setattr(urllib_request, "urlopen", return_catalog)
    config = _explicit_pooled_config(
        pool,
        workspace="offline-success",
    )

    result = recognize(source, config=config)

    assert result.markdown == "# Pooled board\n"
    assert catalog_keys == ["Bearer pool-secret-key-0"]
    assert fake_openai.state.keys == ["pool-secret-key-0"]
    assert [call["model"] for call in fake_openai.state.calls] == ["qwen-vl-max"]
    slot = pool.snapshot().slots[0]
    assert slot.in_flight == 0
    assert slot.selection_count == 1
    assert slot.success_count == 1
    assert slot.failure_count == 0
    assert "pool-secret-key-0" not in repr(result)


def test_pooled_catalog_model_absence_releases_lease_without_sdk_or_failure(
    tmp_path,
    monkeypatch,
) -> None:
    from urllib import request as urllib_request

    source = write_test_image(tmp_path / "board.png", size=(12, 13))
    pool = _pool(1)
    adapter = importlib.import_module("ocrllm.providers.dashscope.recognize_images")
    monkeypatch.setattr(
        adapter,
        "load_openai",
        lambda: pytest.fail("an absent catalog model must stop before SDK loading"),
    )
    monkeypatch.setattr(
        urllib_request,
        "urlopen",
        lambda request, *, timeout: _CatalogResponse("another-model"),
    )

    with pytest.raises(ConfigError, match="DashScope does not serve") as captured:
        recognize(
            source,
            config=_explicit_pooled_config(pool, workspace="offline-absent"),
        )

    assert captured.value.details["provider_calls_attempted"] == 0
    slot = pool.snapshot().slots[0]
    assert slot.in_flight == 0
    assert slot.selection_count == 1
    assert slot.success_count == 0
    assert slot.failure_count == 0


def test_pooled_catalog_outage_releases_lease_before_sdk_loading(
    tmp_path,
    monkeypatch,
) -> None:
    from urllib import request as urllib_request

    source = write_test_image(tmp_path / "board.png", size=(12, 13))
    pool = _pool(1)
    adapter = importlib.import_module("ocrllm.providers.dashscope.recognize_images")
    monkeypatch.setattr(
        adapter,
        "load_openai",
        lambda: pytest.fail("a catalog outage must stop before SDK loading"),
    )

    def raise_catalog_outage(request, *, timeout):
        raise OSError("offline outage")

    monkeypatch.setattr(urllib_request, "urlopen", raise_catalog_outage)

    with pytest.raises(ProviderError) as captured:
        recognize(
            source,
            config=_explicit_pooled_config(pool, workspace="offline-outage"),
        )

    assert captured.value.code == "PROVIDER_CATALOG_UNAVAILABLE"
    assert captured.value.details["provider_calls_attempted"] == 0
    slot = pool.snapshot().slots[0]
    assert slot.in_flight == 0
    assert slot.selection_count == 1
    assert slot.success_count == 0
    assert slot.failure_count == 1


def test_pooled_cancellation_during_catalog_releases_lease_before_sdk_loading(
    tmp_path,
    monkeypatch,
) -> None:
    from urllib import request as urllib_request

    source = write_test_image(tmp_path / "board.png", size=(12, 13))
    pool = _pool(1)
    cancellation = threading.Event()
    adapter = importlib.import_module("ocrllm.providers.dashscope.recognize_images")
    monkeypatch.setattr(
        adapter,
        "load_openai",
        lambda: pytest.fail("catalog cancellation must stop before SDK loading"),
    )

    def cancel_after_catalog(request, *, timeout):
        cancellation.set()
        return _CatalogResponse("qwen-vl-max")

    monkeypatch.setattr(urllib_request, "urlopen", cancel_after_catalog)

    with pytest.raises(Cancelled) as captured:
        recognize(
            source,
            config=_explicit_pooled_config(
                pool,
                workspace="offline-cancelled",
                cancellation=cancellation,
            ),
        )

    assert captured.value.details["provider_calls_attempted"] == 0
    slot = pool.snapshot().slots[0]
    assert slot.in_flight == 0
    assert slot.selection_count == 1
    assert slot.success_count == 0
    assert slot.failure_count == 0


def test_public_recognition_shares_pool_across_primary_and_scout_calls(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png", size=(12, 13))
    pool = _pool(2)
    fake_openai = _FakeOpenAI()
    adapter = importlib.import_module("ocrllm.providers.dashscope.recognize_images")
    monkeypatch.setattr(adapter, "load_openai", lambda: fake_openai)
    resolver = importlib.import_module(
        "ocrllm.providers.dashscope.resolve_dashscope_model"
    )
    monkeypatch.setattr(
        resolver,
        "fetch_dashscope_model_catalog",
        lambda settings, **kwargs: frozenset({"qwen-vl-max"}),
    )

    result = recognize(source, config=_pooled_config(pool, scout=True))

    assert result.markdown == "# Pooled board\n"
    assert fake_openai.state.keys == [
        "pool-secret-key-0",
        "pool-secret-key-1",
        "pool-secret-key-0",
        "pool-secret-key-1",
    ]
    assert [slot.success_count for slot in pool.snapshot().slots] == [2, 2]


def test_provider_failure_updates_pool_for_next_call_without_same_call_retry(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png", size=(12, 13))
    pool = _pool(2, policy=CredentialPoolPolicy(cooldown_seconds=0))
    fake_openai = _FakeOpenAI(fail_first=True)
    adapter = importlib.import_module("ocrllm.providers.dashscope.recognize_images")
    monkeypatch.setattr(adapter, "load_openai", lambda: fake_openai)

    with pytest.raises(RateLimited):
        recognize(source, config=_pooled_config(pool))

    assert fake_openai.state.keys == ["pool-secret-key-0"]
    fake_openai.state.fail_first = False
    result = recognize(source, config=_pooled_config(pool))

    assert result.markdown == "NONE"
    assert fake_openai.state.keys == ["pool-secret-key-0", "pool-secret-key-1"]
