"""Verify bounded, caller-selected real image batches and audio through OCRLLM."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path


IMAGE_MODEL = "qwen3.8-27b-q6-k-medium-ocr"
AUDIO_MODEL = "qwen3-asr-1.7b"


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--image", required=True, type=Path, action="append")
    parser.add_argument("--image-model", default=IMAGE_MODEL)
    parser.add_argument("--audio-model", default=AUDIO_MODEL)
    parser.add_argument("--image-batch-size", type=int, default=1)
    parser.add_argument("--audio-seconds", type=int, default=60)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args(argv)
    if not 1 <= len(args.image) <= 8 or not 1 <= args.image_batch_size <= 8:
        parser.error("Use 1–8 explicitly selected images and batch size 1–8.")
    if not 1 <= args.audio_seconds <= 180 or not 0 < args.timeout <= 600:
        parser.error("Audio must be 1–180 seconds; timeout must be in (0, 600].")
    return args


def run_smoke(arguments: argparse.Namespace) -> dict[str, object]:
    from ocrllm import (
        OpenAICompatibleSettings,
        ProviderModel,
        batchify_images,
        recognize_audio_to_markdown,
        recognize_images_to_markdown,
        split_audio,
    )
    from ocrllm.errors import OCRLLMError

    images = tuple(path.absolute() for path in arguments.image)
    from ocrllm.audio.build_long_audio_interval_windows import (
        LongAudioIntervalWindow,
    )
    from ocrllm.audio.materialize_long_audio_interval import (
        materialize_long_audio_interval,
    )
    from ocrllm.audio.probe_product_mp3 import probe_product_mp3
    audio = arguments.audio.absolute()
    image_before = tuple(_fingerprint(path) for path in images)
    audio_before = _fingerprint(audio)
    if None in image_before or audio_before is None:
        return {"status": "failed", "code": "INVALID_SOURCE_EVIDENCE"}
    settings = OpenAICompatibleSettings(base_url=arguments.base_url)
    image_provider = ProviderModel(
        vendor="local-gateway",
        model=arguments.image_model,
        adapter_id="openai_compatible_chat",
        settings=settings,
        supports_plain_ocr=True,
        supports_detail_ocr=True,
        supports_audio=False,
        default_image_batch_size=arguments.image_batch_size,
        default_audio_minutes=None,
        retry_rules={},
    )
    audio_provider = ProviderModel(
        vendor="local-gateway",
        model=arguments.audio_model,
        adapter_id="openai_compatible_chat",
        settings=settings,
        supports_plain_ocr=False,
        supports_detail_ocr=False,
        supports_audio=True,
        default_image_batch_size=None,
        default_audio_minutes=1,
        retry_rules={},
    )
    with tempfile.TemporaryDirectory(prefix="ocrllm-local-gateway-") as root:
        root_path = Path(root)
        audio_duration = probe_product_mp3(audio)
        window = LongAudioIntervalWindow(
            index=0,
            logical_start_seconds=0.0,
            logical_end_seconds=min(float(arguments.audio_seconds), audio_duration),
            actual_start_seconds=0.0,
            actual_end_seconds=min(float(arguments.audio_seconds), audio_duration),
        )
        try:
            owned_audio = root_path / "source.mp3"
            shutil.copyfile(audio, owned_audio)
            audio_started = time.monotonic()
            with materialize_long_audio_interval(owned_audio, window=window) as clip:
                audio_result = recognize_audio_to_markdown(
                    split_audio(clip, interval_minutes=1, include_boundary_context=False),
                    provider=audio_provider,
                    output_path=root_path / "audio.md",
                    timeout_seconds=arguments.timeout,
                )
            audio_seconds = time.monotonic() - audio_started
            image_started = time.monotonic()
            image_result = recognize_images_to_markdown(
                batchify_images(images, provider=image_provider),
                provider=image_provider,
                image_task="detail_ocr",
                output_path=root_path / "image.md",
                timeout_seconds=arguments.timeout,
            )
        except OCRLLMError as error:
            return {
                "status": "failed",
                "code": error.code,
                "provider_calls_attempted": _safe_int(
                    error.details.get("provider_calls_attempted")
                ),
                "failure_scope": _safe_text(error.details.get("failure_scope")),
                "failed_slots": _safe_failed_slots(error.details.get("failed_slots")),
                "image_source_unchanged": tuple(_fingerprint(path) for path in images) == image_before,
                "audio_source_unchanged": _fingerprint(audio) == audio_before,
            }
        image_seconds = time.monotonic() - image_started
        audio_usage = _single_usage(audio_result.metadata)
        image_usage = _single_usage(image_result.metadata)
        passed = (
            audio_result.status == "complete"
            and image_result.status == "complete"
            and bool(audio_result.markdown.strip())
            and audio_result.metadata.get("no_speech_slot_count") == 0
            and bool(image_result.markdown.strip())
            and audio_result.metadata.get("provider_call_count") == audio_result.metadata.get("slot_count")
            and image_result.metadata.get("provider_call_count") == (len(images) + arguments.image_batch_size - 1) // arguments.image_batch_size
            and audio_usage is not None
            and image_usage is not None
            and audio_usage.get("model") == arguments.audio_model
            and image_usage.get("model") == arguments.image_model
            and tuple(_fingerprint(path) for path in images) == image_before
            and _fingerprint(audio) == audio_before
        )
        return {
            "status": "passed" if passed else "failed",
            "code": None if passed else "INVALID_SCENARIO_EVIDENCE",
            "audio_wall_seconds": round(audio_seconds, 3),
            "image_wall_seconds": round(image_seconds, 3),
            "image_count": len(images),
            "image_batch_size": arguments.image_batch_size,
            "audio_slot_count": audio_result.metadata.get("slot_count"),
            "audio_no_speech_slot_count": audio_result.metadata.get("no_speech_slot_count"),
            "audio_model": audio_usage.get("model") if audio_usage else None,
            "audio_input_tokens": audio_usage.get("input_tokens") if audio_usage else None,
            "audio_output_tokens": audio_usage.get("output_tokens") if audio_usage else None,
            "audio_markdown_nonempty": bool(audio_result.markdown.strip()),
            "image_model": image_usage.get("model") if image_usage else None,
            "image_input_tokens": image_usage.get("input_tokens") if image_usage else None,
            "image_output_tokens": image_usage.get("output_tokens") if image_usage else None,
            "image_markdown_nonempty": bool(image_result.markdown.strip()),
            "image_frame_marker_present": "<!-- meta:frame" in image_result.markdown,
            "audio_provider_call_count": audio_result.metadata.get("provider_call_count"),
            "image_provider_call_count": image_result.metadata.get("provider_call_count"),
            "image_source_unchanged": tuple(_fingerprint(path) for path in images) == image_before,
            "audio_source_unchanged": _fingerprint(audio) == audio_before,
        }


def _single_usage(metadata: Mapping[str, object]) -> Mapping[str, object] | None:
    rows = metadata.get("current_provider_model_usage")
    return rows[0] if type(rows) is tuple and len(rows) == 1 and isinstance(rows[0], Mapping) else None


def _fingerprint(path: Path) -> tuple[int, str] | None:
    try:
        if path.is_symlink() or not path.is_file():
            return None
        data = path.read_bytes()
    except (OSError, ValueError):
        return None
    return len(data), hashlib.sha256(data).hexdigest()


def _safe_int(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None



def _safe_failed_slots(value: object) -> tuple[dict[str, object], ...] | None:
    if type(value) is not tuple:
        return None
    safe = []
    for row in value:
        if not isinstance(row, Mapping):
            return None
        code = _safe_text(row.get("code"))
        model = _safe_text(row.get("model"))
        slot_index = _safe_int(row.get("slot_index"))
        if code is None or model is None or slot_index is None:
            return None
        safe.append({"slot_index": slot_index, "model": model, "code": code})
    return tuple(safe)

def _safe_text(value: object) -> str | None:
    return value if type(value) is str and len(value) <= 128 else None


def main(argv: Sequence[str] | None = None) -> int:
    summary = run_smoke(parse_arguments(argv))
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    return 0 if summary.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
