"""Provider-neutral text and usage from one compatible Chat Completion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OpenAICompatibleChatResponse:
    """Carry one assistant text choice and exact-or-unknown token counts."""

    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None

    def __post_init__(self) -> None:
        if type(self.text) is not str:
            raise TypeError("compatible Chat Completion text must be a string")
        for value in (self.input_tokens, self.output_tokens):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("compatible token usage must be nonnegative")
