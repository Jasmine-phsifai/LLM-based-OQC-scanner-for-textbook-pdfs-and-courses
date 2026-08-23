"""Immutable preflighted values for one Google short-audio request."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class GoogleInlineAudio:
    """Hold one inline MP3 without rendering bytes in repr."""

    data: bytes = field(repr=False)
    mime_type: str = "audio/mpeg"


@dataclass(frozen=True, slots=True)
class GoogleGenAIAudioRequest:
    """Hold a fully preflighted Google short-audio request."""

    model: str
    contents: tuple[str | GoogleInlineAudio, ...] = field(repr=False)
    inline_byte_count: int
    wire_byte_upper_bound: int
