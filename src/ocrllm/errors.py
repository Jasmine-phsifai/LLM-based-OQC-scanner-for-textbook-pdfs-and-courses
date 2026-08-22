"""Typed, machine-readable public OCRLLM failures."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import ClassVar, cast

from .freeze_json_value import FrozenJSONValue, JSONValue, freeze_json_value


STABLE_ERROR_CODES = frozenset(
    {
        "SOURCE_NOT_FOUND",
        "SOURCE_UNREADABLE",
        "SOURCE_INVALID",
        "SOURCE_TOO_LARGE",
        "UNSUPPORTED_FORMAT",
        "DEPENDENCY_MISSING",
        "CONFIG_MISSING",
        "CONFIG_INVALID",
        "PROVIDER_AUTHENTICATION",
        "PROVIDER_PERMISSION_DENIED",
        "PROVIDER_ACCOUNT_SUSPENDED",
        "PROVIDER_RATE_LIMITED",
        "PROVIDER_CONCURRENCY_LIMITED",
        "PROVIDER_QUOTA_EXHAUSTED",
        "ALL_CANDIDATES_EXHAUSTED",
        "PROVIDER_TIMEOUT",
        "PROVIDER_NETWORK",
        "PROVIDER_UNAVAILABLE",
        "PROVIDER_CATALOG_UNAVAILABLE",
        "PROVIDER_REQUEST_INVALID",
        "PROVIDER_CONTENT_BLOCKED",
        "PROVIDER_RESPONSE_INVALID",
        "PROVIDER_REFUSED_RECOGNITION",
        "OCR_BACKEND_FAILED",
        "OCR_RESULT_INVALID",
        "OCR_NO_TEXT",
        "PDF_BACKEND_UNAVAILABLE",
        "PDF_PASSWORD_REQUIRED",
        "PDF_PASSWORD_INVALID",
        "PDF_INVALID",
        "PDF_PAGE_RANGE_INVALID",
        "NO_SPEECH_DETECTED",
        "OUTPUT_EXISTS",
        "OUTPUT_PATH_INVALID",
        "OUTPUT_WRITE_FAILED",
        "RESUME_STATE_INVALID",
        "RESUME_STATE_MISMATCH",
        "CANCELLED",
        "PROTOCOL_UNSUPPORTED",
        "COMMAND_INVALID",
        "WORKER_BUSY",
        "WORKER_INTERNAL",
        "REQUEST_NOT_ACTIVE",
    }
)

_RETRYABLE_BY_DEFAULT = frozenset(
    {
        "PROVIDER_RATE_LIMITED",
        "PROVIDER_CONCURRENCY_LIMITED",
        "PROVIDER_TIMEOUT",
        "PROVIDER_NETWORK",
        "PROVIDER_UNAVAILABLE",
        "PROVIDER_CATALOG_UNAVAILABLE",
    }
)
_REDACTED = "[REDACTED]"
_SENSITIVE_DETAIL_KEY_PARTS = (
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "exception",
    "headers",
    "password",
    "passwd",
    "rawresponse",
    "requestbody",
    "responsebody",
    "secret",
    "token",
    "traceback",
)


class OCRLLMError(Exception):
    """Base class for stable, secret-safe public OCRLLM failures."""

    default_code: ClassVar[str | None] = None
    default_message: ClassVar[str] = "The OCRLLM operation failed."
    allowed_codes: ClassVar[frozenset[str]] = STABLE_ERROR_CODES

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        retryable: bool | None = None,
        details: Mapping[str, JSONValue] | None = None,
    ) -> None:
        resolved_code = code if code is not None else self.default_code
        if resolved_code is None:
            raise TypeError("OCRLLMError requires a stable error code") from None
        if resolved_code not in self.allowed_codes:
            raise ValueError("error code is not valid for this error type") from None

        resolved_message = self.default_message if message is None else message
        if not isinstance(resolved_message, str) or not resolved_message.strip():
            raise TypeError(
                "public error message must be nonempty redacted text"
            ) from None

        if retryable is None:
            resolved_retryable = resolved_code in _RETRYABLE_BY_DEFAULT
        elif isinstance(retryable, bool):
            resolved_retryable = retryable
        else:
            raise TypeError("retryable must be a boolean") from None

        self.code = resolved_code
        self.retryable = resolved_retryable
        self.details = _freeze_redacted_details(details)
        super().__init__(resolved_message)

    def _add_safe_detail(self, key: str, value: JSONValue) -> None:
        """Attach one library-owned detail before the error crosses the facade."""
        merged_details: dict[str, JSONValue] = dict(self.details)
        merged_details[key] = value
        self.details = _freeze_redacted_details(merged_details)


class ConfigError(OCRLLMError):
    """Configuration is missing or invalid."""

    default_code = "CONFIG_INVALID"
    default_message = "Configuration is invalid."
    allowed_codes = frozenset({"CONFIG_MISSING", "CONFIG_INVALID"})


class DependencyMissing(OCRLLMError):
    """A requested optional capability is not installed."""

    default_code = "DEPENDENCY_MISSING"
    default_message = "A required optional dependency is not installed."
    allowed_codes = frozenset({default_code})


class InvalidSource(OCRLLMError):
    """An input source is missing, unreadable, corrupt, empty, or unsafe."""

    default_code = "SOURCE_INVALID"
    default_message = "The input source is invalid."
    allowed_codes = frozenset(
        {"SOURCE_NOT_FOUND", "SOURCE_UNREADABLE", "SOURCE_INVALID", "SOURCE_TOO_LARGE"}
    )


class OutputError(OCRLLMError):
    """Base class for output path and write failures."""

    default_code = "OUTPUT_WRITE_FAILED"
    default_message = "The output operation failed."
    allowed_codes = frozenset(
        {"OUTPUT_EXISTS", "OUTPUT_PATH_INVALID", "OUTPUT_WRITE_FAILED"}
    )


class OutputExists(OutputError):
    """The output target exists or is owned by another recognition."""

    default_code = "OUTPUT_EXISTS"
    default_message = "The output target already exists."
    allowed_codes = frozenset({default_code})


class ResumeStateError(OCRLLMError):
    """Saved recognition work is corrupt or belongs to another request."""

    default_code = "RESUME_STATE_INVALID"
    default_message = "The image resume state is invalid."
    allowed_codes = frozenset({"RESUME_STATE_INVALID", "RESUME_STATE_MISMATCH"})


class ProviderError(OCRLLMError):
    """A provider request failed."""

    default_code = "PROVIDER_RESPONSE_INVALID"
    default_message = "The provider request failed."
    allowed_codes = frozenset(
        {
            "PROVIDER_AUTHENTICATION",
            "PROVIDER_PERMISSION_DENIED",
            "PROVIDER_ACCOUNT_SUSPENDED",
            "PROVIDER_RATE_LIMITED",
            "PROVIDER_CONCURRENCY_LIMITED",
            "PROVIDER_QUOTA_EXHAUSTED",
            "PROVIDER_TIMEOUT",
            "PROVIDER_NETWORK",
            "PROVIDER_UNAVAILABLE",
            "PROVIDER_CATALOG_UNAVAILABLE",
            "PROVIDER_REQUEST_INVALID",
            "PROVIDER_CONTENT_BLOCKED",
            "PROVIDER_RESPONSE_INVALID",
            "PROVIDER_REFUSED_RECOGNITION",
        }
    )


class QuotaExhausted(ProviderError):
    """The configured provider quota was exhausted."""

    default_code = "PROVIDER_QUOTA_EXHAUSTED"
    default_message = "The provider quota is exhausted."
    allowed_codes = frozenset({default_code})


class AllCandidatesExhausted(ProviderError):
    """Every configured model candidate failed with a model-serving disposition."""

    default_code = "ALL_CANDIDATES_EXHAUSTED"
    default_message = "All configured provider model candidates are exhausted."
    allowed_codes = frozenset({default_code})


class ProviderPermissionDenied(ProviderError):
    """A valid provider credential lacks permission for this workflow."""

    default_code = "PROVIDER_PERMISSION_DENIED"
    default_message = "The provider denied permission for this workflow."
    allowed_codes = frozenset({default_code})


class ProviderAccountSuspended(ProviderError):
    """The provider account cannot run work until external account recovery."""

    default_code = "PROVIDER_ACCOUNT_SUSPENDED"
    default_message = "The provider account is suspended."
    allowed_codes = frozenset({default_code})


class RateLimited(ProviderError):
    """The provider temporarily throttled this request."""

    default_code = "PROVIDER_RATE_LIMITED"
    default_message = "The provider temporarily rate-limited the request."
    allowed_codes = frozenset({default_code})


class ConcurrencyLimited(ProviderError):
    """The provider temporarily rejected excess concurrent work."""

    default_code = "PROVIDER_CONCURRENCY_LIMITED"
    default_message = "The provider concurrency limit is active."
    allowed_codes = frozenset({default_code})


class ProviderUnavailable(ProviderError):
    """The provider service was temporarily unavailable."""

    default_code = "PROVIDER_UNAVAILABLE"
    default_message = "The provider service is temporarily unavailable."
    allowed_codes = frozenset({default_code})


class ProviderRequestInvalid(ProviderError):
    """The provider rejected model, endpoint, or request parameters."""

    default_code = "PROVIDER_REQUEST_INVALID"
    default_message = "The provider rejected the request parameters."
    allowed_codes = frozenset({default_code})


class ProviderContentBlocked(ProviderError):
    """The provider rejected the submitted content under its policy."""

    default_code = "PROVIDER_CONTENT_BLOCKED"
    default_message = "The provider blocked the submitted content."
    allowed_codes = frozenset({default_code})


class OCRBackendError(OCRLLMError):
    """A local OCR backend failed or returned an invalid result."""

    default_code = "OCR_BACKEND_FAILED"
    default_message = "The local OCR backend failed."
    allowed_codes = frozenset({"OCR_BACKEND_FAILED", "OCR_RESULT_INVALID"})


class NoTextDetected(OCRLLMError):
    """Local OCR found no text above the configured confidence threshold."""

    default_code = "OCR_NO_TEXT"
    default_message = "No text was detected."
    allowed_codes = frozenset({default_code})


class NoSpeechDetected(OCRLLMError):
    """A valid audio source contained no detected speech."""

    default_code = "NO_SPEECH_DETECTED"
    default_message = "No speech was detected."
    allowed_codes = frozenset({default_code})


class UnsupportedFormat(OCRLLMError):
    """The input format is not supported by the library facade."""

    default_code = "UNSUPPORTED_FORMAT"
    default_message = "The source format is not supported."
    allowed_codes = frozenset({default_code})


class Cancelled(OCRLLMError):
    """Recognition was cancelled by the caller."""

    default_code = "CANCELLED"
    default_message = "Recognition was cancelled."
    allowed_codes = frozenset({default_code})


def _freeze_redacted_details(
    details: Mapping[str, JSONValue] | None,
) -> Mapping[str, FrozenJSONValue]:
    source: object = {} if details is None else details
    if not isinstance(source, Mapping):
        raise TypeError("error details must be a JSON object") from None

    try:
        frozen = freeze_json_value(source)
    except (TypeError, ValueError):
        raise ValueError("error details must contain only finite JSON values") from None

    if not isinstance(frozen, Mapping):
        raise TypeError("error details must be a JSON object") from None
    return _redact_frozen_mapping(cast(Mapping[str, FrozenJSONValue], frozen))


def _redact_frozen_mapping(
    value: Mapping[str, FrozenJSONValue],
) -> Mapping[str, FrozenJSONValue]:
    redacted: dict[str, FrozenJSONValue] = {}
    for key, item in value.items():
        if _is_sensitive_detail_key(key):
            redacted[key] = _REDACTED
        else:
            redacted[key] = _redact_frozen_value(item)
    return MappingProxyType(redacted)


def _redact_frozen_value(value: FrozenJSONValue) -> FrozenJSONValue:
    if isinstance(value, Mapping):
        return _redact_frozen_mapping(value)
    if isinstance(value, tuple):
        return tuple(_redact_frozen_value(item) for item in value)
    return value


def _is_sensitive_detail_key(key: str) -> bool:
    normalized = "".join(
        character for character in key.casefold() if character.isalnum()
    )
    return any(part in normalized for part in _SENSITIVE_DETAIL_KEY_PARTS)
