import math

import pytest

from ocrllm.errors import (
    Cancelled,
    ConcurrencyLimited,
    ConfigError,
    DependencyMissing,
    InvalidSource,
    NoSpeechDetected,
    OCRLLMError,
    OutputError,
    OutputExists,
    PDFError,
    ProviderError,
    ProviderAccountSuspended,
    ProviderContentBlocked,
    ProviderPermissionDenied,
    ProviderRequestInvalid,
    ProviderUnavailable,
    QuotaExhausted,
    RateLimited,
    ResumeStateError,
    UnsupportedFormat,
    VideoError,
)


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ConfigError(), "CONFIG_INVALID"),
        (DependencyMissing(), "DEPENDENCY_MISSING"),
        (InvalidSource(), "SOURCE_INVALID"),
        (OutputError(), "OUTPUT_WRITE_FAILED"),
        (OutputExists(), "OUTPUT_EXISTS"),
        (PDFError(), "PDF_INVALID"),
        (VideoError(), "VIDEO_INVALID"),
        (ProviderError(), "PROVIDER_RESPONSE_INVALID"),
        (QuotaExhausted(), "PROVIDER_QUOTA_EXHAUSTED"),
        (ProviderPermissionDenied(), "PROVIDER_PERMISSION_DENIED"),
        (ProviderAccountSuspended(), "PROVIDER_ACCOUNT_SUSPENDED"),
        (ProviderRequestInvalid(), "PROVIDER_REQUEST_INVALID"),
        (ProviderContentBlocked(), "PROVIDER_CONTENT_BLOCKED"),
        (NoSpeechDetected(), "NO_SPEECH_DETECTED"),
        (UnsupportedFormat(), "UNSUPPORTED_FORMAT"),
        (Cancelled(), "CANCELLED"),
    ],
)
def test_public_error_defaults_have_stable_codes(error, code):
    assert isinstance(error, OCRLLMError)
    assert error.code == code
    assert error.retryable is False
    assert error.details == {}


def test_video_error_accepts_missing_audio_stream_code():
    error = VideoError(code="VIDEO_NO_AUDIO_STREAM")

    assert error.code == "VIDEO_NO_AUDIO_STREAM"


def test_resume_state_error_default_is_media_neutral():
    error = ResumeStateError()

    assert error.code == "RESUME_STATE_INVALID"
    assert str(error) == "The saved recognition state is invalid."


def test_provider_retryability_defaults_follow_stable_failure_category():
    assert ProviderError(code="PROVIDER_NETWORK").retryable is True
    assert ProviderError(code="PROVIDER_TIMEOUT").retryable is True
    assert RateLimited().retryable is True
    assert ConcurrencyLimited().retryable is True
    assert ProviderUnavailable().retryable is True
    assert ProviderError(code="PROVIDER_AUTHENTICATION").retryable is False
    assert QuotaExhausted().retryable is False
    assert ProviderPermissionDenied().retryable is False
    assert ProviderAccountSuspended().retryable is False
    assert ProviderRequestInvalid().retryable is False
    assert ProviderContentBlocked().retryable is False


def test_existing_error_names_still_accept_redacted_public_messages():
    error = ConfigError("Config.provider is required", code="CONFIG_MISSING")

    assert str(error) == "Config.provider is required"
    assert error.code == "CONFIG_MISSING"


def test_error_details_are_copied_frozen_and_known_secrets_are_redacted():
    api_secret = "DETAIL-API-SECRET-1a2b"
    password_secret = "DETAIL-PASSWORD-SECRET-3c4d"
    original = {
        "status_code": 429,
        "context": {"api_key": api_secret, "password": password_secret},
        "attempts": [1, 2],
    }

    error = ProviderError(code="PROVIDER_NETWORK", details=original)
    original["status_code"] = 500
    original["attempts"].append(3)  # type: ignore[union-attr]

    assert error.details["status_code"] == 429
    assert error.details["attempts"] == (1, 2)
    context = error.details["context"]
    assert context["api_key"] == "[REDACTED]"  # type: ignore[index]
    assert context["password"] == "[REDACTED]"  # type: ignore[index]
    assert api_secret not in repr(error)
    assert password_secret not in repr(error)
    with pytest.raises(TypeError):
        error.details["status_code"] = 200  # type: ignore[index]
    with pytest.raises(TypeError):
        context["api_key"] = "changed"  # type: ignore[index]


def test_numeric_usage_tokens_remain_visible_but_token_secrets_stay_redacted():
    secret = "DETAIL-TOKEN-SECRET-a91f"
    error = ProviderError(
        details={
            "usage": {
                "input_tokens": 17,
                "output_tokens": None,
                "provider_token": secret,
            },
            "invalid_usage": {
                "input_tokens": secret,
                "output_tokens": -1,
            },
        }
    )

    usage = error.details["usage"]
    invalid_usage = error.details["invalid_usage"]
    assert usage["input_tokens"] == 17  # type: ignore[index]
    assert usage["output_tokens"] is None  # type: ignore[index]
    assert usage["provider_token"] == "[REDACTED]"  # type: ignore[index]
    assert invalid_usage["input_tokens"] == "[REDACTED]"  # type: ignore[index]
    assert invalid_usage["output_tokens"] == "[REDACTED]"  # type: ignore[index]
    assert secret not in repr(error.details)


@pytest.mark.parametrize("bad_detail", [math.nan, math.inf, object()])
def test_error_details_reject_unsupported_values_without_stringifying_them(bad_detail):
    secret = "DETAIL-INVALID-SECRET-9981"

    with pytest.raises(ValueError) as caught:
        ProviderError(details={"provider_token": secret, "bad": bad_detail})

    assert secret not in str(caught.value)
    assert secret not in repr(caught.value)


def test_arbitrary_exception_objects_are_not_used_as_public_messages():
    secret = "RAW-EXCEPTION-SECRET-76dd"

    with pytest.raises(TypeError) as caught:
        ProviderError(RuntimeError(secret))  # type: ignore[arg-type]

    assert secret not in str(caught.value)
    assert secret not in repr(caught.value)


def test_error_type_rejects_an_unrelated_code_without_echoing_it():
    secret_code = "SECRET-CODE-4f3a"

    with pytest.raises(ValueError) as caught:
        InvalidSource(code=secret_code)

    assert secret_code not in str(caught.value)
    assert secret_code not in repr(caught.value)
