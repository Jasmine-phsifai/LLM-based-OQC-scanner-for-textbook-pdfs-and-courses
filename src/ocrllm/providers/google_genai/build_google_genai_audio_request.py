"""Build one bounded native Google short-audio request."""

from __future__ import annotations

import json
from pathlib import Path

from ...errors import InvalidSource
from ...raise_if_cancelled import raise_if_cancelled
from .google_genai_audio_request import GoogleGenAIAudioRequest, GoogleInlineAudio


MAX_GOOGLE_AUDIO_WIRE_BYTES = 20_000_000
_WIRE_BODY_OVERHEAD_BYTES = 512
_WIRE_PART_OVERHEAD_BYTES = 128
_MIME_TYPE = "audio/mpeg"


def build_google_genai_audio_request(
    snapshot_path: Path,
    *,
    prompt: str,
    model: str,
    cancellation: object | None = None,
) -> GoogleGenAIAudioRequest:
    """Read one owned MP3 and reject an oversized wire body locally."""
    raise_if_cancelled(cancellation)
    wire_without_data = (
        _WIRE_BODY_OVERHEAD_BYTES
        + _WIRE_PART_OVERHEAD_BYTES
        + _json_string_byte_count(model)
        + _json_string_byte_count(prompt)
        + _json_string_byte_count(_MIME_TYPE)
    )
    data = _read_bounded(
        Path(snapshot_path),
        remaining_wire_bytes=MAX_GOOGLE_AUDIO_WIRE_BYTES - wire_without_data,
    )
    wire_bytes = wire_without_data + 4 * ((len(data) + 2) // 3)
    if wire_bytes >= MAX_GOOGLE_AUDIO_WIRE_BYTES:
        _raise_too_large()
    return GoogleGenAIAudioRequest(
        model=model,
        contents=(prompt, GoogleInlineAudio(data=data)),
        inline_byte_count=len(data),
        wire_byte_upper_bound=wire_bytes,
    )


def _json_string_byte_count(value: str) -> int:
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def _read_bounded(path: Path, *, remaining_wire_bytes: int) -> bytes:
    maximum_source_bytes = max(0, ((remaining_wire_bytes - 1) // 4) * 3)
    try:
        expected_size = path.stat().st_size
        with path.open("rb") as stream:
            data = stream.read(maximum_source_bytes + 1)
    except FileNotFoundError:
        raise InvalidSource(
            "The validated MP3 snapshot is no longer available.",
            code="SOURCE_NOT_FOUND",
        ) from None
    except MemoryError:
        _raise_too_large()
    except (OSError, ValueError):
        raise InvalidSource(
            "The validated MP3 snapshot cannot be read.",
            code="SOURCE_UNREADABLE",
        ) from None
    if len(data) > maximum_source_bytes:
        _raise_too_large()
    if len(data) != expected_size:
        raise InvalidSource(
            "The validated MP3 snapshot changed during Google preflight.",
            code="SOURCE_INVALID",
        ) from None
    return data


def _raise_too_large() -> None:
    raise InvalidSource(
        "The Google GenAI audio request exceeds the inline wire limit.",
        code="SOURCE_TOO_LARGE",
        details={"maximum_inline_wire_bytes": MAX_GOOGLE_AUDIO_WIRE_BYTES},
    ) from None
