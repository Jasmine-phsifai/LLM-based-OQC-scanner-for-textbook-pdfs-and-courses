"""Fingerprint one short-audio request embedded in a video job."""

from __future__ import annotations

import hashlib
import json

from .audio.transcription_prompt import AUDIO_TRANSCRIPTION_PROMPT


VIDEO_SHORT_AUDIO_IDENTITY_VERSION = "ocrllm.video-short-audio.v1"


def fingerprint_video_short_audio_request(
    *,
    source_sha256: str,
    model: str,
) -> str:
    """Hash output-affecting short-audio facts without credentials."""
    document = {
        "identity_version": VIDEO_SHORT_AUDIO_IDENTITY_VERSION,
        "source_sha256": source_sha256,
        "provider": "google",
        "model": model,
        "transport": "google_inline",
        "prompt_sha256": hashlib.sha256(
            AUDIO_TRANSCRIPTION_PROMPT.encode("utf-8")
        ).hexdigest(),
    }
    encoded = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
