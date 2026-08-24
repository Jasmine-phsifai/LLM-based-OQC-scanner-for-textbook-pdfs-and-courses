"""Lazy public OCRLLM library facade."""

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .audio_model_settings import AudioModelSettings as AudioModelSettings
    from .batch_item_outcome import BatchItemOutcome as BatchItemOutcome
    from .capability_report import CapabilityReport as CapabilityReport
    from .config import Config as Config
    from .credential_pool_policy import CredentialPoolPolicy as CredentialPoolPolicy
    from .errors import (
        AllCandidatesExhausted as AllCandidatesExhausted,
        Cancelled as Cancelled,
        ConcurrencyLimited as ConcurrencyLimited,
        ConfigError as ConfigError,
        DependencyMissing as DependencyMissing,
        InvalidSource as InvalidSource,
        NoSpeechDetected as NoSpeechDetected,
        NoTextDetected as NoTextDetected,
        OCRBackendError as OCRBackendError,
        OCRLLMError as OCRLLMError,
        OutputError as OutputError,
        OutputExists as OutputExists,
        PDFError as PDFError,
        ProviderAccountSuspended as ProviderAccountSuspended,
        ProviderContentBlocked as ProviderContentBlocked,
        ProviderError as ProviderError,
        ProviderPermissionDenied as ProviderPermissionDenied,
        ProviderRequestInvalid as ProviderRequestInvalid,
        ProviderUnavailable as ProviderUnavailable,
        QuotaExhausted as QuotaExhausted,
        RateLimited as RateLimited,
        ResumeStateError as ResumeStateError,
        UnsupportedFormat as UnsupportedFormat,
    )
    from .get_capabilities import get_capabilities as get_capabilities
    from .local_ocr_settings import LocalOCRSettings as LocalOCRSettings
    from .provider_error_disposition import (
        ProviderErrorDisposition as ProviderErrorDisposition,
        get_provider_error_disposition as get_provider_error_disposition,
    )
    from .providers.dashscope.credential import (
        DashScopeCredential as DashScopeCredential,
    )
    from .providers.dashscope.credential_pool import (
        DashScopeCredentialPool as DashScopeCredentialPool,
    )
    from .providers.dashscope.credential_pool_report import (
        DashScopeCredentialPoolReport as DashScopeCredentialPoolReport,
        DashScopeCredentialSlotReport as DashScopeCredentialSlotReport,
    )
    from .providers.dashscope.provider_settings import (
        DashScopeSettings as DashScopeSettings,
    )
    from .providers.google_genai.list_google_genai_models import (
        list_google_genai_models as list_google_genai_models,
    )
    from .providers.google_genai.provider_settings import (
        GoogleGenAISettings as GoogleGenAISettings,
    )
    from .recognition_execution_policy import (
        RecognitionExecutionPolicy as RecognitionExecutionPolicy,
    )
    from .recognition_preferences import (
        RecognitionPreferences as RecognitionPreferences,
    )
    from .recognize import recognize as recognize
    from .recognize_batch import recognize_batch as recognize_batch
    from .result import RecognitionResult as RecognitionResult
    from .vision_model_settings import VisionModelSettings as VisionModelSettings


_PUBLIC_IMPORTS = {
    "AudioModelSettings": (".audio_model_settings", "AudioModelSettings"),
    "AllCandidatesExhausted": (".errors", "AllCandidatesExhausted"),
    "BatchItemOutcome": (".batch_item_outcome", "BatchItemOutcome"),
    "Cancelled": (".errors", "Cancelled"),
    "CapabilityReport": (".capability_report", "CapabilityReport"),
    "ConcurrencyLimited": (".errors", "ConcurrencyLimited"),
    "Config": (".config", "Config"),
    "ConfigError": (".errors", "ConfigError"),
    "CredentialPoolPolicy": (".credential_pool_policy", "CredentialPoolPolicy"),
    "DashScopeCredential": (
        ".providers.dashscope.credential",
        "DashScopeCredential",
    ),
    "DashScopeCredentialPool": (
        ".providers.dashscope.credential_pool",
        "DashScopeCredentialPool",
    ),
    "DashScopeCredentialPoolReport": (
        ".providers.dashscope.credential_pool_report",
        "DashScopeCredentialPoolReport",
    ),
    "DashScopeCredentialSlotReport": (
        ".providers.dashscope.credential_pool_report",
        "DashScopeCredentialSlotReport",
    ),
    "DashScopeSettings": (
        ".providers.dashscope.provider_settings",
        "DashScopeSettings",
    ),
    "DependencyMissing": (".errors", "DependencyMissing"),
    "InvalidSource": (".errors", "InvalidSource"),
    "GoogleGenAISettings": (
        ".providers.google_genai.provider_settings",
        "GoogleGenAISettings",
    ),
    "LocalOCRSettings": (".local_ocr_settings", "LocalOCRSettings"),
    "NoSpeechDetected": (".errors", "NoSpeechDetected"),
    "NoTextDetected": (".errors", "NoTextDetected"),
    "OCRBackendError": (".errors", "OCRBackendError"),
    "OCRLLMError": (".errors", "OCRLLMError"),
    "OutputError": (".errors", "OutputError"),
    "OutputExists": (".errors", "OutputExists"),
    "PDFError": (".errors", "PDFError"),
    "ProviderAccountSuspended": (".errors", "ProviderAccountSuspended"),
    "ProviderContentBlocked": (".errors", "ProviderContentBlocked"),
    "ProviderError": (".errors", "ProviderError"),
    "ProviderErrorDisposition": (
        ".provider_error_disposition",
        "ProviderErrorDisposition",
    ),
    "ProviderPermissionDenied": (".errors", "ProviderPermissionDenied"),
    "ProviderRequestInvalid": (".errors", "ProviderRequestInvalid"),
    "ProviderUnavailable": (".errors", "ProviderUnavailable"),
    "QuotaExhausted": (".errors", "QuotaExhausted"),
    "RateLimited": (".errors", "RateLimited"),
    "RecognitionExecutionPolicy": (
        ".recognition_execution_policy",
        "RecognitionExecutionPolicy",
    ),
    "RecognitionPreferences": (
        ".recognition_preferences",
        "RecognitionPreferences",
    ),
    "RecognitionResult": (".result", "RecognitionResult"),
    "ResumeStateError": (".errors", "ResumeStateError"),
    "UnsupportedFormat": (".errors", "UnsupportedFormat"),
    "VisionModelSettings": (".vision_model_settings", "VisionModelSettings"),
    "get_capabilities": (".get_capabilities", "get_capabilities"),
    "list_google_genai_models": (
        ".providers.google_genai.list_google_genai_models",
        "list_google_genai_models",
    ),
    "get_provider_error_disposition": (
        ".provider_error_disposition",
        "get_provider_error_disposition",
    ),
    "recognize": (".recognize", "recognize"),
    "recognize_batch": (".recognize_batch", "recognize_batch"),
}

__all__ = [
    "AudioModelSettings",
    "BatchItemOutcome",
    "Cancelled",
    "ConcurrencyLimited",
    "Config",
    "AllCandidatesExhausted",
    "CredentialPoolPolicy",
    "CapabilityReport",
    "ConfigError",
    "DashScopeSettings",
    "DashScopeCredential",
    "DashScopeCredentialPool",
    "DashScopeCredentialPoolReport",
    "DashScopeCredentialSlotReport",
    "DependencyMissing",
    "InvalidSource",
    "GoogleGenAISettings",
    "LocalOCRSettings",
    "NoTextDetected",
    "NoSpeechDetected",
    "OCRBackendError",
    "OCRLLMError",
    "OutputError",
    "OutputExists",
    "PDFError",
    "ProviderError",
    "ProviderAccountSuspended",
    "ProviderContentBlocked",
    "ProviderErrorDisposition",
    "ProviderPermissionDenied",
    "ProviderRequestInvalid",
    "ProviderUnavailable",
    "QuotaExhausted",
    "RateLimited",
    "ResumeStateError",
    "RecognitionResult",
    "RecognitionExecutionPolicy",
    "RecognitionPreferences",
    "UnsupportedFormat",
    "VisionModelSettings",
    "recognize",
    "recognize_batch",
    "get_capabilities",
    "list_google_genai_models",
    "get_provider_error_disposition",
]
__version__ = "0.1.0"


def __getattr__(name: str):
    """Load one public API object on first access."""
    try:
        module_name, attribute_name = _PUBLIC_IMPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None

    from importlib import import_module

    if name in {"recognize", "recognize_batch"}:
        recognize_value = getattr(import_module(".recognize", __name__), "recognize")
        batch_value = getattr(
            import_module(".recognize_batch", __name__),
            "recognize_batch",
        )
        globals()["recognize"] = recognize_value
        globals()["recognize_batch"] = batch_value
        return globals()[name]

    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Include lazy public names in interactive discovery."""
    return sorted(set(globals()) | set(_PUBLIC_IMPORTS))
