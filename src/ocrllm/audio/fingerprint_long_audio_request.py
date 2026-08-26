"""Fingerprint one whole-file or interval long-audio request."""

from __future__ import annotations

import hashlib
import json
import re

from .build_long_audio_interval_prompt import LONG_AUDIO_INTERVAL_PROMPT_VERSION
from .build_long_audio_interval_windows import LongAudioIntervalWindow
from .transcription_prompt import AUDIO_TRANSCRIPTION_PROMPT_VERSION
from .validate_long_audio_interval_window import validate_long_audio_interval_window


LONG_AUDIO_REQUEST_IDENTITY_VERSION = "ocrllm.long-audio-request.v2"
_SHA256 = re.compile(r"[0-9a-f]{64}")


def fingerprint_long_audio_request(
    *,
    source_sha256: str,
    mode: str,
    provider: str,
    model: str,
    transport: str,
    window: LongAudioIntervalWindow | None = None,
) -> str:
    """Hash every settled output-affecting fact for one audio request."""
    if type(source_sha256) is not str or _SHA256.fullmatch(source_sha256) is None:
        raise ValueError("source_sha256 must be canonical lowercase SHA-256") from None
    _validate_identity_text(provider, field_name="provider")
    _validate_identity_text(model, field_name="model")
    _validate_identity_text(transport, field_name="transport")

    if type(mode) is not str or mode not in ("whole", "interval"):
        raise ValueError("mode must be exactly 'whole' or 'interval'") from None
    if mode == "whole":
        if window is not None:
            raise ValueError("whole mode must not include an interval window") from None
        prompt_version = AUDIO_TRANSCRIPTION_PROMPT_VERSION
        window_document = None
    else:
        if window is None:
            raise ValueError("interval mode requires an interval window") from None
        validate_long_audio_interval_window(window)
        prompt_version = LONG_AUDIO_INTERVAL_PROMPT_VERSION
        window_document = {
            "index": window.index,
            "logical_start_seconds": window.logical_start_seconds,
            "logical_end_seconds": window.logical_end_seconds,
            "actual_start_seconds": window.actual_start_seconds,
            "actual_end_seconds": window.actual_end_seconds,
        }

    document = {
        "identity_version": LONG_AUDIO_REQUEST_IDENTITY_VERSION,
        "source_sha256": source_sha256,
        "mode": mode,
        "provider": provider,
        "model": model,
        "transport": transport,
        "prompt_version": prompt_version,
        "window": window_document,
    }
    encoded = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_identity_text(value: object, *, field_name: str) -> None:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValueError(f"{field_name} must be nonempty exact text") from None
