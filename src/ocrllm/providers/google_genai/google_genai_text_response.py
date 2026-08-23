"""Provider-neutral text and usage from Google generateContent."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GoogleGenAITextResponse:
    """Carry one extracted Google text response and optional token counts."""

    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None

    def __post_init__(self) -> None:
        for value in (self.input_tokens, self.output_tokens):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("provider token usage must be nonnegative integers")
