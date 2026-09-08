"""Build one bounded MP3 Chat Completions transcription request."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field
from typing import Any

from ...audio.snapshot_long_mp3 import LongMP3Snapshot
from ...audio.snapshot_short_mp3 import MAX_SHORT_MP3_SOURCE_BYTES
from ...errors import ConfigError, InvalidSource


@dataclass(frozen=True, slots=True, kw_only=True)
class OpenAICompatibleAudioRequest:
    """Hold request values without exposing Base64 audio in repr."""

    _model: str = field(repr=False)
    _prompt: str | None = field(repr=False)
    _send_audio_prompt: bool = field(repr=False)
    _audio_base64: str = field(repr=False)

    @property
    def kwargs(self) -> dict[str, Any]:
        """Return fresh containers for one Chat Completions request."""
        content: list[dict[str, Any]] = []
        if self._send_audio_prompt:
            content.append({"type": "text", "text": self._prompt})
        content.append(
            {
                "type": "input_audio",
                "input_audio": {
                    "data": self._audio_base64,
                    "format": "mp3",
                },
            }
        )
        return {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": content,
                }
            ],
        }


def build_openai_compatible_audio_request(
    snapshot: LongMP3Snapshot,
    *,
    prompt: str | None,
    model: str,
    send_audio_prompt: bool = True,
) -> OpenAICompatibleAudioRequest:
    """Verify one exact MP3 clip and encode raw Base64 audio."""
    if type(snapshot) is not LongMP3Snapshot:
        raise InvalidSource(
            "The compatible audio request requires an exact MP3 snapshot.",
            code="SOURCE_INVALID",
        ) from None
    if type(send_audio_prompt) is not bool:
        raise ConfigError(
            "OpenAI-compatible audio recognition requires a boolean "
            "send_audio_prompt setting.",
            code="CONFIG_INVALID",
        ) from None
    if send_audio_prompt and (type(prompt) is not str or not prompt.strip()):
        raise ConfigError(
            "OpenAI-compatible audio recognition requires a nonempty prompt.",
            code="CONFIG_INVALID",
        ) from None
    if type(model) is not str or not model or model != model.strip():
        raise ConfigError(
            "OpenAI-compatible audio recognition requires an exact model name.",
            code="CONFIG_INVALID",
        ) from None
    if snapshot.byte_size > MAX_SHORT_MP3_SOURCE_BYTES:
        raise InvalidSource(
            "The compatible inline MP3 clip exceeds the 25 MiB safety limit.",
            code="SOURCE_TOO_LARGE",
            details={
                "byte_size": snapshot.byte_size,
                "maximum_byte_size": MAX_SHORT_MP3_SOURCE_BYTES,
            },
        ) from None
    source_bytes = _read_exact_snapshot(snapshot)
    try:
        encoded = base64.b64encode(source_bytes).decode("ascii")
    except MemoryError:
        raise InvalidSource(
            "The MP3 clip could not be encoded within memory limits.",
            code="SOURCE_TOO_LARGE",
        ) from None
    finally:
        del source_bytes
    return OpenAICompatibleAudioRequest(
        _model=model,
        _prompt=prompt,
        _send_audio_prompt=send_audio_prompt,
        _audio_base64=encoded,
    )


def _read_exact_snapshot(snapshot: LongMP3Snapshot) -> bytes:
    try:
        with snapshot.path.open("rb") as source_stream:
            source_bytes = source_stream.read(MAX_SHORT_MP3_SOURCE_BYTES + 1)
    except FileNotFoundError:
        raise InvalidSource(
            "The validated MP3 snapshot is no longer available.",
            code="SOURCE_NOT_FOUND",
        ) from None
    except (OSError, ValueError):
        raise InvalidSource(
            "The validated MP3 snapshot cannot be read.",
            code="SOURCE_UNREADABLE",
        ) from None
    if (
        len(source_bytes) != snapshot.byte_size
        or hashlib.sha256(source_bytes).hexdigest() != snapshot.sha256
    ):
        raise InvalidSource(
            "The validated MP3 snapshot changed during request preparation.",
            code="SOURCE_INVALID",
        ) from None
    return source_bytes
