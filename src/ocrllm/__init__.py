"""Lazy public OCRLLM library facade."""

from typing import TYPE_CHECKING

# Bind lightweight facade functions before callers can import their same-named
# submodules and replace these public package attributes.
from .batchify_images import batchify_images as batchify_images
from .split_audio import split_audio as split_audio
from .compose_video_result import compose_video_result as compose_video_result
from .publish_video_result import publish_video_result as publish_video_result
from .recognize import recognize as recognize
from .recognize_batch import recognize_batch as recognize_batch
from .recognize_long_mp3 import recognize_long_mp3 as recognize_long_mp3
from .recognize_images_to_markdown import (
    recognize_images_to_markdown as recognize_images_to_markdown,
)
from .resume_images_to_markdown import (
    resume_images_to_markdown as resume_images_to_markdown,
)
from .recognize_video import recognize_video as recognize_video
from .recognize_video_frames import recognize_video_frames as recognize_video_frames
from .recognize_video_to_markdown import (
    recognize_video_to_markdown as recognize_video_to_markdown,
)


if TYPE_CHECKING:
    from .audio_model_settings import AudioModelSettings as AudioModelSettings
    from .audio_slice import AudioSlice as AudioSlice
    from .batch_item_outcome import BatchItemOutcome as BatchItemOutcome
    from .batchify_images import batchify_images as batchify_images
    from .split_audio import split_audio as split_audio
    from .capability_report import CapabilityReport as CapabilityReport
    from .config import Config as Config
    from .compose_video_result import compose_video_result as compose_video_result
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
        VideoError as VideoError,
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
    from .providers.provider_model import ProviderModel as ProviderModel
    from .providers.provider_model_presets import (
        DASHSCOPE_QWEN3_5_OCR_CN_BEIJING as DASHSCOPE_QWEN3_5_OCR_CN_BEIJING,
        GOOGLE_GEMINI_2_5_FLASH as GOOGLE_GEMINI_2_5_FLASH,
    )
    from .publish_video_result import publish_video_result as publish_video_result
    from .recognition_execution_policy import (
        RecognitionExecutionPolicy as RecognitionExecutionPolicy,
    )
    from .recognition_preferences import (
        RecognitionPreferences as RecognitionPreferences,
    )
    from .recognize import recognize as recognize
    from .recognize_batch import recognize_batch as recognize_batch
    from .recognize_long_mp3 import recognize_long_mp3 as recognize_long_mp3
    from .recognize_images_to_markdown import (
        recognize_images_to_markdown as recognize_images_to_markdown,
    )
    from .resume_images_to_markdown import (
        resume_images_to_markdown as resume_images_to_markdown,
    )
    from .recognize_video_frames import (
        recognize_video_frames as recognize_video_frames,
    )
    from .recognize_video import recognize_video as recognize_video
    from .recognize_video_to_markdown import (
        recognize_video_to_markdown as recognize_video_to_markdown,
    )
    from .retained_video_frame import RetainedVideoFrame as RetainedVideoFrame
    from .result import RecognitionResult as RecognitionResult
    from .video.extract_video_frames import extract_video_frames as extract_video_frames
    from .video.extract_video_audio import extract_video_audio as extract_video_audio
    from .video.inspect_video import inspect_video as inspect_video
    from .video_info import VideoInfo as VideoInfo
    from .video_recognition_outcome import (
        VideoRecognitionOutcome as VideoRecognitionOutcome,
    )
    from .vision_model_settings import VisionModelSettings as VisionModelSettings


_PUBLIC_IMPORTS = {
    "AudioModelSettings": (".audio_model_settings", "AudioModelSettings"),
    "AudioSlice": (".audio_slice", "AudioSlice"),
    "AllCandidatesExhausted": (".errors", "AllCandidatesExhausted"),
    "BatchItemOutcome": (".batch_item_outcome", "BatchItemOutcome"),
    "batchify_images": (".batchify_images", "batchify_images"),
    "split_audio": (".split_audio", "split_audio"),
    "Cancelled": (".errors", "Cancelled"),
    "CapabilityReport": (".capability_report", "CapabilityReport"),
    "ConcurrencyLimited": (".errors", "ConcurrencyLimited"),
    "Config": (".config", "Config"),
    "compose_video_result": (".compose_video_result", "compose_video_result"),
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
    "ProviderModel": (".providers.provider_model", "ProviderModel"),
    "GOOGLE_GEMINI_2_5_FLASH": (
        ".providers.provider_model_presets",
        "GOOGLE_GEMINI_2_5_FLASH",
    ),
    "DASHSCOPE_QWEN3_5_OCR_CN_BEIJING": (
        ".providers.provider_model_presets",
        "DASHSCOPE_QWEN3_5_OCR_CN_BEIJING",
    ),
    "ProviderRequestInvalid": (".errors", "ProviderRequestInvalid"),
    "ProviderUnavailable": (".errors", "ProviderUnavailable"),
    "publish_video_result": (".publish_video_result", "publish_video_result"),
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
    "RetainedVideoFrame": (".retained_video_frame", "RetainedVideoFrame"),
    "ResumeStateError": (".errors", "ResumeStateError"),
    "UnsupportedFormat": (".errors", "UnsupportedFormat"),
    "VideoError": (".errors", "VideoError"),
    "VisionModelSettings": (".vision_model_settings", "VisionModelSettings"),
    "VideoInfo": (".video_info", "VideoInfo"),
    "VideoRecognitionOutcome": (
        ".video_recognition_outcome",
        "VideoRecognitionOutcome",
    ),
    "get_capabilities": (".get_capabilities", "get_capabilities"),
    "extract_video_frames": (".video.extract_video_frames", "extract_video_frames"),
    "extract_video_audio": (".video.extract_video_audio", "extract_video_audio"),
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
    "recognize_long_mp3": (".recognize_long_mp3", "recognize_long_mp3"),
    "recognize_images_to_markdown": (
        ".recognize_images_to_markdown",
        "recognize_images_to_markdown",
    ),
    "resume_images_to_markdown": (
        ".resume_images_to_markdown",
        "resume_images_to_markdown",
    ),
    "recognize_video_frames": (
        ".recognize_video_frames",
        "recognize_video_frames",
    ),
    "recognize_video": (".recognize_video", "recognize_video"),
    "recognize_video_to_markdown": (
        ".recognize_video_to_markdown",
        "recognize_video_to_markdown",
    ),
    "inspect_video": (".video.inspect_video", "inspect_video"),
}

__all__ = [
    "AudioModelSettings",
    "AudioSlice",
    "BatchItemOutcome",
    "batchify_images",
    "split_audio",
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
    "ProviderModel",
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
    "RetainedVideoFrame",
    "RecognitionExecutionPolicy",
    "RecognitionPreferences",
    "UnsupportedFormat",
    "VideoError",
    "VideoInfo",
    "VideoRecognitionOutcome",
    "VisionModelSettings",
    "compose_video_result",
    "publish_video_result",
    "recognize",
    "recognize_batch",
    "recognize_long_mp3",
    "recognize_images_to_markdown",
    "resume_images_to_markdown",
    "recognize_video_frames",
    "recognize_video",
    "recognize_video_to_markdown",
    "extract_video_frames",
    "extract_video_audio",
    "inspect_video",
    "get_capabilities",
    "list_google_genai_models",
    "get_provider_error_disposition",
    "GOOGLE_GEMINI_2_5_FLASH",
    "DASHSCOPE_QWEN3_5_OCR_CN_BEIJING",
]
__version__ = "0.1.0"


def __getattr__(name: str):
    """Load one public API object on first access."""
    try:
        module_name, attribute_name = _PUBLIC_IMPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None

    from importlib import import_module

    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Include lazy public names in interactive discovery."""
    return sorted(set(globals()) | set(_PUBLIC_IMPORTS))
