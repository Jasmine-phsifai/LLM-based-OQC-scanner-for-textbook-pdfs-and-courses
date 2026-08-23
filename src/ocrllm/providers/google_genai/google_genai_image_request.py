"""Immutable preflighted values for one Google image request."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class GoogleInlineImage:
    """Hold one ordered inline image without rendering bytes in repr."""

    data: bytes = field(repr=False)
    mime_type: str


@dataclass(frozen=True, slots=True)
class GoogleGenAIImageRequest:
    """Hold a fully preflighted Google generateContent request."""

    model: str
    contents: tuple[GoogleInlineImage | str, ...] = field(repr=False)
    inline_byte_count: int
    wire_byte_upper_bound: int
