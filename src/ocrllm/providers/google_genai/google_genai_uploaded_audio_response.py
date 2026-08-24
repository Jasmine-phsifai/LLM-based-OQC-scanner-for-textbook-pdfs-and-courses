"""Successful Google Files audio response plus cleanup state."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GoogleGenAIUploadedAudioResponse:
    """Carry transcript usage without hiding remote or client cleanup failure."""

    markdown: str
    input_tokens: int | None
    output_tokens: int | None
    remote_file_deleted: bool
    client_closed: bool
