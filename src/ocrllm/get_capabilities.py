"""Report the frozen shared registry without network calls or optional imports."""

from __future__ import annotations

from .capability_report import CapabilityReport
from .config import Config
from .providers.dashscope.resolve_dashscope_model import DEFAULT_DASHSCOPE_MODEL
from .providers.dashscope.provider_settings import DashScopeSettings
from .snapshot_config import snapshot_config


_CAPABILITY_NAMES = (
    "image.board.png",
    "image.board.jpeg",
    "image.ocr.rapidocr",
    "provider.dashscope.vision",
    "provider.dashscope.audio-short",
    "provider.dashscope.filetrans",
    "worker.jsonl.v1alpha1",
    "worker.jsonl.v1alpha2",
    "pdf.text",
    "pdf.vision",
    "pdf.text.resume",
    "pdf.vision.resume",
    "audio.short.wav-pcm-s16",
    "audio.short.mp3-mpeg-layer3",
    "audio.short.m4a-aac-lc",
    "audio.long.wav-pcm-s16",
    "audio.long.mp3-mpeg-layer3",
    "audio.long.m4a-aac-lc",
    "video.mp4-h264",
    "video.mp4-h264-aac",
)
_DEFERRED_REASON_BY_CAPABILITY = {
    "provider.dashscope.audio-short": (
        "Stage A1 shipped only the direct Google short-audio path; "
        "DashScope short audio remains deferred."
    ),
    "provider.dashscope.filetrans": "Intentionally deferred to Stage A2.",
    "worker.jsonl.v1alpha2": "Intentionally deferred to Phase 3.",
    "pdf.text": "Intentionally deferred to Phase 3.",
    "pdf.vision": (
        "The direct PDF vision facade is implemented and live-proven; "
        "shared capability/worker registration remains deferred."
    ),
    "pdf.text.resume": "Intentionally deferred to Phase 3.",
    "pdf.vision.resume": (
        "Direct PDF recognition reuses ordinary image sidecars for "
        "offline-proven resume; shared capability/worker registration "
        "remains deferred."
    ),
    "audio.short.wav-pcm-s16": (
        "Intentionally deferred to a later audio-format gate."
    ),
    "audio.short.mp3-mpeg-layer3": (
        "The experimental direct Google short-MP3 API is live-proven; "
        "shared worker support remains deferred."
    ),
    "audio.short.m4a-aac-lc": (
        "Intentionally deferred to a later audio-format gate."
    ),
    "audio.long.wav-pcm-s16": (
        "Intentionally deferred to a later audio-format gate."
    ),
    "audio.long.mp3-mpeg-layer3": (
        "The standalone direct Google Files long-MP3 API is live-proven; "
        "shared capability/worker registration remains deferred."
    ),
    "audio.long.m4a-aac-lc": (
        "Intentionally deferred to a later audio-format gate."
    ),
    "video.mp4-h264": "Intentionally deferred to Phase 5.",
    "video.mp4-h264-aac": "Intentionally deferred to Phase 5.",
}


def get_capabilities(config: Config | None = None) -> tuple[CapabilityReport, ...]:
    """Return deterministic reports for the shared capability/worker registry."""

    if config is None:
        image_status = "available"
        image_reason = (
            "Phase 1 implementation, live quality, and packaging gates passed."
        )
        provider_status = "unavailable"
        provider_reason = (
            "Explicit DashScope region and endpoint settings are required for use."
        )
        local_ocr_status = "available"
        local_ocr_reason = (
            "The Phase 2A maintained RapidOCR implementation, real offline, "
            "fresh-extra, and clean packaging gates passed."
        )
    else:
        validated = snapshot_config(config)
        image_status, image_reason, provider_status, provider_reason = (
            _configured_image_status(validated)
        )
        if validated.image_mode == "ocr":
            local_ocr_status = "available"
            local_ocr_reason = (
                "The explicit config selects the live-proven Phase 2A local-OCR "
                "workflow."
            )
        else:
            local_ocr_status = "unavailable"
            local_ocr_reason = "The explicit config selects provider-backed vision."

    reports: list[CapabilityReport] = []
    for name in _CAPABILITY_NAMES:
        if name in {"image.board.png", "image.board.jpeg"}:
            reports.append(
                CapabilityReport(name=name, status=image_status, reason=image_reason)
            )
        elif name == "image.ocr.rapidocr":
            reports.append(
                CapabilityReport(
                    name=name,
                    status=local_ocr_status,
                    reason=local_ocr_reason,
                )
            )
        elif name == "provider.dashscope.vision":
            reports.append(
                CapabilityReport(
                    name=name,
                    status=provider_status,
                    reason=provider_reason,
                )
            )
        elif name == "worker.jsonl.v1alpha1":
            reports.append(
                CapabilityReport(
                    name=name,
                    status="available",
                    reason=(
                        "The Phase 2 command, event, process isolation, Node, "
                        "cancellation, production, live, and packaging gates passed. "
                        "Packaged Electron compatibility remains a Phase 6 gate."
                    ),
                )
            )
        else:
            reports.append(
                CapabilityReport(
                    name=name,
                    status="deferred",
                    reason=_DEFERRED_REASON_BY_CAPABILITY[name],
                )
            )
    return tuple(reports)


def _configured_image_status(
    config: Config,
) -> tuple[str, str, str, str]:
    if config.image_mode == "ocr":
        return (
            "available",
            "The explicit configuration selects the live-proven Phase 2A local-OCR workflow.",
            "unavailable",
            "The explicit configuration does not select an API vision provider.",
        )
    if config.provider is None:
        reason = "The explicit configuration has no vision provider."
        return "unavailable", reason, "unavailable", reason
    if type(config.provider) is not DashScopeSettings:
        return (
            "experimental",
            "An injected provider satisfies the offline protocol only; no stable live identity is proven.",
            "unavailable",
            "The explicit configuration does not select the built-in DashScope provider.",
        )
    settings = config.provider
    is_exact_v17 = (
        (
            config.vision_model.name is None
            or config.vision_model.name == DEFAULT_DASHSCOPE_MODEL
        )
        and settings.region == "cn-beijing"
        and settings.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
        and settings.enable_thinking is True
        and settings.vl_high_resolution_images is True
        and settings.standalone_sign_scout_model == DEFAULT_DASHSCOPE_MODEL
    )
    if is_exact_v17:
        reason = (
            "The exact pinned Beijing v17 workflow passed live and packaging gates."
        )
        return "available", reason, "available", reason
    reason = (
        "The DashScope workflow is configured and offline-valid but differs from "
        "the exact live-proven v17 workflow."
    )
    return "experimental", reason, "experimental", reason
