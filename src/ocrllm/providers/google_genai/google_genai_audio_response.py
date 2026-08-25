"""Structured successful response from Google audio recognition."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GoogleGenAIAudioResponse:
    """Carry transcript, usage, and the settled local-client cleanup state."""

    markdown: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    client_closed: bool = True

    def __post_init__(self) -> None:
        for value in (self.input_tokens, self.output_tokens):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("provider token usage must be nonnegative integers")
