"""Offline tests for DashScope credential, cancellation, response, and errors."""

from __future__ import annotations

import builtins
from types import SimpleNamespace

import pytest

from ocrllm import (
    Cancelled,
    ConcurrencyLimited,
    ConfigError,
    DashScopeSettings,
    DependencyMissing,
    InvalidSource,
    ProviderError,
    ProviderAccountSuspended,
    ProviderContentBlocked,
    ProviderPermissionDenied,
    ProviderRequestInvalid,
    ProviderUnavailable,
    QuotaExhausted,
    RateLimited,
)
from ocrllm.providers.dashscope.map_dashscope_error import map_dashscope_error
from ocrllm.providers.dashscope.load_openai import load_openai
from ocrllm.providers.dashscope.parse_dashscope_image_response import (
    parse_dashscope_image_response,
)
from ocrllm.providers.dashscope.parse_dashscope_raw_response import (
    parse_dashscope_raw_response,
)
from ocrllm.providers.dashscope.resolve_dashscope_credential import (
    resolve_dashscope_credential,
)
from ocrllm.providers.vision_provider_response import VisionProviderResponse
from ocrllm.raise_if_cancelled import raise_if_cancelled


MODEL = "qwen3.7-plus-2026-05-26"


class InjectedProvider:
    def recognize_images(self, image_paths, *, prompt, config):
        return "# unused\n"


class Signal:
    def __init__(self, value: object) -> None:
        self.value = value

    def is_set(self):
        return self.value


class SdkTimeout(Exception):
    pass


class SdkConnection(Exception):
    pass


class SdkAuthentication(Exception):
    pass


class SdkPermission(Exception):
    pass


class SdkRateLimit(Exception):
    pass


class SdkInternal(Exception):
    pass


OPENAI_SHAPE = SimpleNamespace(
    APITimeoutError=SdkTimeout,
    APIConnectionError=SdkConnection,
    AuthenticationError=SdkAuthentication,
    PermissionDeniedError=SdkPermission,
    RateLimitError=SdkRateLimit,
    InternalServerError=SdkInternal,
)


def test_explicit_dashscope_key_precedes_environment(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "environment-key")

    assert resolve_dashscope_credential(_settings(api_key="explicit-key")) == "explicit-key"


def test_dashscope_key_falls_back_to_environment(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "environment-key")

    assert (
        resolve_dashscope_credential(_settings())
        == "environment-key"
    )


@pytest.mark.parametrize("value", [None, ""])
def test_missing_dashscope_key_is_typed(monkeypatch, value):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    if value is not None:
        monkeypatch.setenv("DASHSCOPE_API_KEY", value)

    with pytest.raises(ConfigError) as captured:
        resolve_dashscope_credential(_settings())

    assert captured.value.code == "CONFIG_MISSING"


@pytest.mark.parametrize(
    "value",
    [" padded-secret ", "line1\nline2-secret", "secret\x7fvalue"],
)
def test_malformed_environment_key_is_invalid_without_echo(monkeypatch, value):
    monkeypatch.setenv("DASHSCOPE_API_KEY", value)

    with pytest.raises(ConfigError) as captured:
        resolve_dashscope_credential(_settings())

    assert captured.value.code == "CONFIG_INVALID"
    assert value not in str(captured.value)
    assert value not in repr(captured.value.details)


def test_coding_plan_key_is_rejected_without_echo(monkeypatch):
    sentinel = "sk-sp-DO_NOT_ECHO_88f4"
    monkeypatch.setenv("DASHSCOPE_API_KEY", sentinel)

    with pytest.raises(ConfigError) as captured:
        resolve_dashscope_credential(_settings())

    assert captured.value.code == "CONFIG_INVALID"
    assert sentinel not in str(captured.value)
    assert sentinel not in repr(captured.value.details)


def _settings(*, api_key: str | None = None) -> DashScopeSettings:
    return DashScopeSettings(
        region="cn-beijing",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=api_key,
    )


def test_missing_openai_extra_is_a_typed_dependency_failure(monkeypatch):
    original_import = builtins.__import__

    def import_without_openai(name, *args, **kwargs):
        if name == "openai":
            raise ModuleNotFoundError("test-only missing OpenAI")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_openai)

    with pytest.raises(DependencyMissing) as captured:
        load_openai()

    assert captured.value.code == "DEPENDENCY_MISSING"
    assert captured.value.details["extra"] == "dashscope"


def test_unsupported_openai_version_is_a_typed_dependency_failure(monkeypatch):
    original_import = builtins.__import__
    fake_openai = SimpleNamespace(__version__="2.29.0", OpenAI=lambda **kwargs: None)

    def import_old_openai(name, *args, **kwargs):
        if name == "openai":
            return fake_openai
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_old_openai)

    with pytest.raises(DependencyMissing) as captured:
        load_openai()

    assert captured.value.code == "DEPENDENCY_MISSING"
    assert captured.value.details["installed_version"] == "2.29.0"


def test_event_compatible_cancellation_is_honored():
    raise_if_cancelled(Signal(False))

    with pytest.raises(Cancelled) as captured:
        raise_if_cancelled(Signal(True))

    assert captured.value.code == "CANCELLED"


@pytest.mark.parametrize("signal", [object(), Signal(1)])
def test_invalid_cancellation_signal_is_configuration_error(signal):
    with pytest.raises(ConfigError) as captured:
        raise_if_cancelled(signal)

    assert captured.value.code == "CONFIG_INVALID"


def _response(
    content="# Board\n",
    *,
    finish_reason="stop",
    refusal=None,
    model=MODEL,
    usage=None,
):
    message = SimpleNamespace(content=content, refusal=refusal, role="assistant")
    choice = SimpleNamespace(message=message, finish_reason=finish_reason, index=0)
    return SimpleNamespace(choices=[choice], model=model, usage=usage)


def test_dashscope_response_parser_returns_text_and_compatible_usage():
    parsed = parse_dashscope_image_response(
        _response(
            usage=SimpleNamespace(prompt_tokens=22, completion_tokens=16),
        ),
        model=MODEL,
    )

    assert parsed == VisionProviderResponse(
        markdown="# Board\n",
        input_tokens=22,
        output_tokens=16,
    )


@pytest.mark.parametrize(
    "usage",
    (
        None,
        object(),
        SimpleNamespace(prompt_tokens=True, completion_tokens=-1),
        SimpleNamespace(prompt_tokens="22", completion_tokens=16.0),
        SimpleNamespace(input_tokens=22, output_tokens=16, total_tokens=38),
    ),
)
def test_dashscope_response_parser_keeps_missing_or_invalid_usage_unknown(usage):
    parsed = parse_dashscope_image_response(_response(usage=usage), model=MODEL)

    assert parsed.markdown == "# Board\n"
    assert parsed.input_tokens is None
    assert parsed.output_tokens is None


def test_dashscope_response_parser_preserves_each_valid_usage_side_independently():
    parsed = parse_dashscope_image_response(
        _response(
            usage=SimpleNamespace(prompt_tokens=22, completion_tokens="unknown"),
        ),
        model=MODEL,
    )

    assert parsed.input_tokens == 22
    assert parsed.output_tokens is None


@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(choices=[]),
        _response(content=None),
        _response(finish_reason="length"),
        _response(finish_reason="content_filter"),
        _response(refusal="request refused"),
        _response(refusal={"reason": "safety"}),
        _response(model="different-model"),
        SimpleNamespace(
            choices=[
                _response().choices[0],
                _response(finish_reason="length").choices[0],
            ],
            model=MODEL,
        ),
    ],
)
def test_dashscope_response_parser_rejects_false_success(response):
    with pytest.raises(ProviderError) as captured:
        parse_dashscope_image_response(response, model=MODEL)

    assert captured.value.code == "PROVIDER_RESPONSE_INVALID"
    assert captured.value.retryable is False


def test_dashscope_raw_response_rejects_timeout_partial_header():
    raw = SimpleNamespace(
        headers={"x-dashscope-partialresponse": "true"},
        parse=lambda: _response(),
    )

    with pytest.raises(ProviderError) as captured:
        parse_dashscope_raw_response(raw, model=MODEL)

    assert captured.value.code == "PROVIDER_RESPONSE_INVALID"


def test_dashscope_raw_response_accepts_absent_or_false_partial_header():
    for headers in ({}, {"x-dashscope-partialresponse": "false"}):
        parsed = _response()
        raw = SimpleNamespace(headers=headers, parse=lambda parsed=parsed: parsed)

        assert parse_dashscope_raw_response(raw, model=MODEL) is parsed


@pytest.mark.parametrize(
    ("error", "expected_type", "expected_code", "retryable"),
    [
        (SdkTimeout(), ProviderError, "PROVIDER_TIMEOUT", True),
        (SdkConnection(), ProviderError, "PROVIDER_NETWORK", True),
        (
            SdkAuthentication(),
            ProviderError,
            "PROVIDER_AUTHENTICATION",
            False,
        ),
        (
            SdkPermission(),
            ProviderPermissionDenied,
            "PROVIDER_PERMISSION_DENIED",
            False,
        ),
        (SdkRateLimit(), RateLimited, "PROVIDER_RATE_LIMITED", True),
        (SdkInternal(), ProviderUnavailable, "PROVIDER_UNAVAILABLE", True),
    ],
)
def test_dashscope_sdk_errors_map_to_stable_categories(
    error,
    expected_type,
    expected_code,
    retryable,
):
    mapped = map_dashscope_error(error, openai_module=OPENAI_SHAPE, model=MODEL)

    assert isinstance(mapped, expected_type)
    assert mapped.code == expected_code
    assert mapped.retryable is retryable
    assert mapped.details["provider"] == "dashscope"
    assert mapped.details["model"] == MODEL


def test_dashscope_transient_throttle_is_not_mislabeled_as_spent_quota():
    error = SdkRateLimit()
    error.status_code = 429
    error.body = {"error": {"code": "Throttling.RateQuota"}}

    mapped = map_dashscope_error(error, openai_module=OPENAI_SHAPE, model=MODEL)

    assert isinstance(mapped, RateLimited)
    assert mapped.code == "PROVIDER_RATE_LIMITED"
    assert mapped.retryable is True
    assert mapped.details["provider_code"] == "Throttling.RateQuota"


def test_dashscope_billing_quota_failure_is_nonretryable():
    error = SdkRateLimit()
    error.status_code = 429
    error.body = {"code": "CommodityNotPurchased"}

    mapped = map_dashscope_error(error, openai_module=OPENAI_SHAPE, model=MODEL)

    assert isinstance(mapped, QuotaExhausted)
    assert mapped.code == "PROVIDER_QUOTA_EXHAUSTED"
    assert mapped.retryable is False
    # The commodity is activated per model: another candidate may be activated.
    assert mapped.details["failure_scope"] == "model"


@pytest.mark.parametrize("status", [400, 403, 429])
def test_dashscope_provider_code_precedes_generic_http_classification(
    status,
):
    error = RuntimeError("raw provider body")
    error.status_code = status
    error.body = {"code": "AllocationQuota.FreeTierOnly"}

    mapped = map_dashscope_error(error, openai_module=OPENAI_SHAPE, model=MODEL)

    assert isinstance(mapped, QuotaExhausted)
    assert mapped.code == "PROVIDER_QUOTA_EXHAUSTED"
    assert mapped.retryable is False
    # Free-tier quota is granted per model: one model's exhaustion must not
    # poison sibling candidates on the same account (audit finding G3).
    assert mapped.details["failure_scope"] == "model"


@pytest.mark.parametrize(
    "quota_marker",
    ["AllocationQuota.FreeTierOnly", "FreeAllocationQuotaExceeded"],
)
def test_dashscope_production_message_only_quota_marker_precedes_http_403(
    quota_marker,
):
    error = RuntimeError(f"private prefix: {quota_marker}: private suffix")
    error.status_code = 403

    mapped = map_dashscope_error(error, openai_module=OPENAI_SHAPE, model=MODEL)

    assert isinstance(mapped, QuotaExhausted)
    assert mapped.code == "PROVIDER_QUOTA_EXHAUSTED"
    assert mapped.retryable is False
    assert mapped.details["failure_scope"] == "model"
    assert "provider_code" not in mapped.details
    assert "private prefix" not in str(mapped)
    assert "private suffix" not in repr(mapped.details)


@pytest.mark.parametrize(
    "provider_code",
    ["Arrearage", "PrepaidBillOverdue", "PostpaidBillOverdue", "AccountSuspended"],
)
def test_dashscope_account_state_failures_are_not_quota_or_authentication(
    provider_code,
):
    error = RuntimeError("raw provider body")
    error.status_code = 400
    error.body = {"code": provider_code}

    mapped = map_dashscope_error(error, openai_module=OPENAI_SHAPE, model=MODEL)

    assert isinstance(mapped, ProviderAccountSuspended)
    assert mapped.code == "PROVIDER_ACCOUNT_SUSPENDED"
    assert mapped.retryable is False
    assert mapped.details["failure_scope"] == "account"


def test_dashscope_data_inspection_failure_is_not_mislabeled_as_config():
    error = RuntimeError("raw provider body")
    error.status_code = 400
    error.body = {"code": "DataInspectionFailed"}

    mapped = map_dashscope_error(error, openai_module=OPENAI_SHAPE, model=MODEL)

    assert isinstance(mapped, ProviderContentBlocked)
    assert mapped.code == "PROVIDER_CONTENT_BLOCKED"
    assert mapped.retryable is False
    assert mapped.details["failure_scope"] == "request"


@pytest.mark.parametrize(
    "provider_code",
    ["RequestTimeOut", "InternalError.Timeout", "ResponseTimeout"],
)
def test_dashscope_documented_timeout_codes_precede_generic_http_500(
    provider_code,
):
    error = RuntimeError("raw provider body")
    error.status_code = 500
    error.body = {"code": provider_code}

    mapped = map_dashscope_error(error, openai_module=OPENAI_SHAPE, model=MODEL)

    assert isinstance(mapped, ProviderError)
    assert mapped.code == "PROVIDER_TIMEOUT"
    assert mapped.retryable is True
    assert mapped.details["provider_code"] == provider_code


def test_dashscope_bad_model_or_endpoint_is_provider_request_error():
    error = RuntimeError("raw provider body must not escape")
    error.status_code = 404
    error.code = "ModelNotFound"
    error.request_id = "req-safe-123"

    mapped = map_dashscope_error(error, openai_module=OPENAI_SHAPE, model=MODEL)

    assert isinstance(mapped, ProviderRequestInvalid)
    assert mapped.code == "PROVIDER_REQUEST_INVALID"
    assert mapped.details["http_status"] == 404
    assert mapped.details["request_id"] == "req-safe-123"
    assert "raw provider body" not in str(mapped)


@pytest.mark.parametrize(
    ("provider_code", "failure_scope"),
    [
        ("AccessDenied", "credential"),
        ("AccessDenied.Unpurchased", "account"),
        ("Model.AccessDenied", "model"),
        ("Workspace.AccessDenied", "credential"),
        ("Endpoint.AccessDenied", "model"),
        ("NotAuthorized", "credential"),
    ],
)
def test_dashscope_permission_codes_are_not_mislabeled_as_authentication(
    provider_code,
    failure_scope,
):
    error = RuntimeError("raw provider body")
    error.status_code = 403
    error.body = {"code": provider_code}

    mapped = map_dashscope_error(error, openai_module=OPENAI_SHAPE, model=MODEL)

    assert isinstance(mapped, ProviderPermissionDenied)
    assert mapped.code == "PROVIDER_PERMISSION_DENIED"
    assert mapped.details["failure_scope"] == failure_scope


@pytest.mark.parametrize(
    "provider_code",
    [
        "Throttling.RateQuota",
        "Throttling.BurstRate",
        "LimitRequests",
        "insufficient_quota",
    ],
)
def test_dashscope_rate_codes_cool_down_the_shared_account(provider_code):
    error = SdkRateLimit()
    error.status_code = 429
    error.body = {"code": provider_code}

    mapped = map_dashscope_error(error, openai_module=OPENAI_SHAPE, model=MODEL)

    assert isinstance(mapped, RateLimited)
    assert mapped.details["failure_scope"] == "account"
    assert mapped.details["limit_kind"] == "rate"


@pytest.mark.parametrize(
    "body",
    [
        {"code": "ConcurrencyLimitExceeded"},
        {
            "code": "Throttling.AllocationQuota",
            "message": "concurrency allocated quota exceeded",
        },
        {
            "error": {
                "code": "Throttling",
                "message": "Too many concurrent requests; limit exceeded",
            }
        },
    ],
)
def test_dashscope_concurrency_failures_are_distinct_from_rate(body):
    error = SdkRateLimit()
    error.status_code = 429
    error.body = body

    mapped = map_dashscope_error(error, openai_module=OPENAI_SHAPE, model=MODEL)

    assert isinstance(mapped, ConcurrencyLimited)
    assert mapped.code == "PROVIDER_CONCURRENCY_LIMITED"
    assert mapped.retryable is True
    assert mapped.details["failure_scope"] == "account"
    assert mapped.details["limit_kind"] == "concurrency"


@pytest.mark.parametrize(
    ("status", "code"),
    [(413, "SOURCE_TOO_LARGE"), (415, "SOURCE_INVALID")],
)
def test_dashscope_provider_media_rejections_remain_source_errors(status, code):
    error = RuntimeError("raw provider body")
    error.status_code = status

    mapped = map_dashscope_error(error, openai_module=OPENAI_SHAPE, model=MODEL)

    assert isinstance(mapped, InvalidSource)
    assert mapped.code == code


def test_dashscope_hostile_error_properties_cannot_cross_boundary():
    sentinel = "HOSTILE_DASHSCOPE_ERROR_SECRET_c4d8"

    class HostileError(Exception):
        @property
        def status_code(self):
            raise RuntimeError(sentinel)

        @property
        def code(self):
            raise RuntimeError(sentinel)

        @property
        def body(self):
            raise RuntimeError(sentinel)

        @property
        def request_id(self):
            raise RuntimeError(sentinel)

        @property
        def message(self):
            raise RuntimeError(sentinel)

    mapped = map_dashscope_error(
        HostileError(),
        openai_module=OPENAI_SHAPE,
        model=MODEL,
    )

    assert mapped.code == "PROVIDER_RESPONSE_INVALID"
    assert sentinel not in str(mapped)
    assert sentinel not in repr(mapped.details)
