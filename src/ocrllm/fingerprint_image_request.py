"""Build one secret-free canonical identity for resumable image work."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from .config import Config
from .contracts.source_fingerprint import SourceFingerprint
from .errors import ConfigError
from .image_request_identity import ImageRequestIdentity
from .providers.dashscope.provider_settings import DashScopeSettings
from .providers.dashscope.resolve_dashscope_model import resolve_dashscope_model
from .thaw_json_value import thaw_json_value


_VISION_PROCESSOR_NAME = "image.vision.board"
_VISION_PROCESSOR_VERSION = "image.vision.board.v1"
_OCR_PROCESSOR_NAME = "image.ocr.rapidocr"
_OCR_PROCESSOR_VERSION = "image.ocr.rapidocr.v1"


def fingerprint_image_request(
    sources: Sequence[SourceFingerprint],
    *,
    profile: str,
    config: Config,
) -> ImageRequestIdentity:
    """Hash all output-affecting image settings while excluding secrets."""
    if config.image_mode == "ocr":
        assert config.local_ocr is not None
        processor_name = _OCR_PROCESSOR_NAME
        processor_version = _OCR_PROCESSOR_VERSION
        provider_document = None
        local_ocr_document = {
            "minimum_confidence": config.local_ocr.minimum_confidence,
        }
        model_document = None
    else:
        processor_name = _VISION_PROCESSOR_NAME
        processor_version = _VISION_PROCESSOR_VERSION
        local_ocr_document = None
        if type(config.provider) is DashScopeSettings:
            settings = config.provider
            provider_document = {
                "name": "dashscope",
                "region": settings.region,
                "base_url": settings.base_url,
                "enable_thinking": settings.enable_thinking,
                "vl_high_resolution_images": settings.vl_high_resolution_images,
                "standalone_sign_scout_model": settings.standalone_sign_scout_model,
            }
            model_document = {
                "name": resolve_dashscope_model(config.vision_model.name),
                "maximum_images_per_request": (
                    config.vision_model.maximum_images_per_request
                ),
            }
        else:
            provider_document = {
                "name": "injected",
                "resume_identity": _injected_provider_resume_identity(config.provider),
            }
            model_document = {
                "name": config.vision_model.name,
                "maximum_images_per_request": (
                    config.vision_model.maximum_images_per_request
                ),
            }

    document = {
        "identity_version": "ocrllm.image-request.v1",
        "sources": [
            {
                "uri": source.uri,
                "byte_size": source.byte_size,
                "sha256": source.sha256,
            }
            for source in sources
        ],
        "processor_name": processor_name,
        "processor_version": processor_version,
        "image_mode": config.image_mode,
        "profile": profile,
        "input_languages": list(config.input_languages),
        "output_language": config.output_language,
        "provider": provider_document,
        "vision_model": model_document,
        "local_ocr": local_ocr_document,
        "preferences": {
            "draft_candidates": config.preferences.draft_candidates,
            "review_passes": config.preferences.review_passes,
        },
        "execution": {
            "maximum_images_per_request": (
                config.execution.maximum_images_per_request
            ),
            "max_parallel_requests": config.execution.max_parallel_requests,
            "provider_request_start_interval_seconds": (
                config.execution.provider_request_start_interval_seconds
            ),
        },
        "timeout_seconds": config.timeout_seconds,
        "extra": thaw_json_value(config.extra),
    }
    encoded = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return ImageRequestIdentity(
        request_fingerprint=hashlib.sha256(encoded).hexdigest(),
        processor_name=processor_name,
        processor_version=processor_version,
        sources=tuple(sources),
    )


def _injected_provider_resume_identity(provider: object) -> str:
    """Return the caller-declared identity that makes an injected provider resumable.

    The library cannot infer whether two injected provider objects would produce
    the same recognition, so reuse is opt-in: the provider declares a
    ``resume_identity`` string that changes whenever its behaviour changes.
    """
    if provider is None:
        raise ConfigError(
            "Image resume requires a configured provider or local OCR mode.",
            code="CONFIG_INVALID",
        ) from None
    try:
        identity = getattr(provider, "resume_identity", None)
    except Exception:
        identity = None
    if type(identity) is not str or not identity.strip():
        raise ConfigError(
            "Image resume with an injected provider requires a nonempty "
            "'resume_identity' string attribute on the provider that changes "
            "whenever its recognition behaviour changes.",
            code="CONFIG_INVALID",
        ) from None
    return identity
