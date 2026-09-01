"""Validate generic compatible image/audio requests from two real sources."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import tempfile
from collections.abc import Sequence
from pathlib import Path


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Require one image and one MP3 without exposing their contents."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    return parser.parse_args(argv)


def run_request_smoke(arguments: argparse.Namespace) -> dict[str, object]:
    """Exercise public planning and internal wire builders with no network."""
    image = arguments.image.absolute()
    audio = arguments.audio.absolute()
    before_image = _fingerprint(image)
    before_audio = _fingerprint(audio)
    if before_image is None or before_audio is None:
        return {"status": "failed", "code": "INVALID_SOURCE_EVIDENCE"}

    from ocrllm import OpenAICompatibleSettings, ProviderModel, batchify_images, split_audio
    from ocrllm.audio.build_long_audio_interval_upload_snapshot import (
        build_long_audio_interval_upload_snapshot,
    )
    from ocrllm.audio.materialize_long_audio_interval import (
        materialize_long_audio_interval,
    )
    from ocrllm.audio.snapshot_product_mp3 import snapshot_product_mp3
    from ocrllm.providers.openai_compatible.build_openai_compatible_audio_request import (
        build_openai_compatible_audio_request,
    )
    from ocrllm.providers.openai_compatible.build_openai_compatible_image_request import (
        build_openai_compatible_image_request,
    )

    image_provider = _provider(
        ProviderModel,
        OpenAICompatibleSettings,
        model="future-image-model",
        image=True,
    )
    audio_provider = _provider(
        ProviderModel,
        OpenAICompatibleSettings,
        model="future-audio-model",
        image=False,
    )
    batches = batchify_images((image,), provider=image_provider)
    image_request = build_openai_compatible_image_request(
        batches[0],
        prompt="Recognize this real image.",
        model=image_provider.model,
    ).kwargs
    data_url = image_request["messages"][0]["content"][0]["image_url"]["url"]
    image_payload = base64.b64decode(data_url.split(",", 1)[1])

    with tempfile.TemporaryDirectory(prefix="ocrllm-compatible-request-") as root:
        with snapshot_product_mp3(audio, temp_dir=Path(root)) as snapshot:
            slices = split_audio(
                snapshot.path,
                interval_minutes=1,
                include_boundary_context=False,
            )
            first = slices[0]
            with materialize_long_audio_interval(
                snapshot.path,
                window=_window(first),
            ) as segment:
                segment_snapshot = build_long_audio_interval_upload_snapshot(
                    segment,
                    duration_seconds=first.actual_end_seconds - first.actual_start_seconds,
                )
                audio_request = build_openai_compatible_audio_request(
                    segment_snapshot,
                    prompt="Transcribe this exact real clip.",
                    model=audio_provider.model,
                ).kwargs
                audio_part = audio_request["messages"][0]["content"][1]["input_audio"]
                audio_payload = base64.b64decode(audio_part["data"])
                audio_payload_matches = (
                    hashlib.sha256(audio_payload).hexdigest() == segment_snapshot.sha256
                )
                clip_seconds = segment_snapshot.duration_seconds

    passed = (
        image_payload == image.read_bytes()
        and image_request["model"] == image_provider.model
        and audio_request["model"] == audio_provider.model
        and audio_part["format"] == "mp3"
        and not audio_part["data"].startswith("data:")
        and audio_payload_matches
        and clip_seconds == 60.0
        and _fingerprint(image) == before_image
        and _fingerprint(audio) == before_audio
    )
    return {
        "status": "passed" if passed else "failed",
        "code": None if passed else "INVALID_SCENARIO_EVIDENCE",
        "image_source_bytes": before_image[0],
        "audio_source_bytes": before_audio[0],
        "image_payload_bytes": len(image_payload),
        "audio_payload_bytes": len(audio_payload),
        "audio_clip_seconds": clip_seconds,
        "image_model_forwarded": image_request["model"] == image_provider.model,
        "audio_model_forwarded": audio_request["model"] == audio_provider.model,
        "image_source_unchanged": _fingerprint(image) == before_image,
        "audio_source_unchanged": _fingerprint(audio) == before_audio,
        "provider_call_count": 0,
    }


def _provider(ProviderModel, Settings, *, model: str, image: bool):
    return ProviderModel(
        vendor="future-gateway",
        model=model,
        adapter_id="openai_compatible_chat",
        settings=Settings(
            base_url="http://127.0.0.1:1/v1",
            api_key_env="FUTURE_GATEWAY_KEY",
        ),
        supports_plain_ocr=image,
        supports_detail_ocr=image,
        supports_audio=not image,
        default_image_batch_size=1 if image else None,
        default_audio_minutes=None if image else 1,
        retry_rules={},
    )


def _window(item):
    from ocrllm.audio.build_long_audio_interval_windows import LongAudioIntervalWindow

    return LongAudioIntervalWindow(
        index=item.index,
        logical_start_seconds=item.logical_start_seconds,
        logical_end_seconds=item.logical_end_seconds,
        actual_start_seconds=item.actual_start_seconds,
        actual_end_seconds=item.actual_end_seconds,
    )


def _fingerprint(path: Path) -> tuple[int, str] | None:
    try:
        if path.is_symlink() or not path.is_file():
            return None
        data = path.read_bytes()
    except (OSError, ValueError):
        return None
    return len(data), hashlib.sha256(data).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    summary = run_request_smoke(parse_arguments(argv))
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    return 0 if summary.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
