"""Provider-neutral successful response for one audio recognition call."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AudioProviderResponse:
    """Carry transcript, usage, and aggregate provider cleanup state."""

    markdown: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    provider_cleanup_failed: bool = False

    def __post_init__(self) -> None:
        if type(self.markdown) is not str or not self.markdown.strip():
            raise ValueError("audio provider Markdown must contain text")
        for value in (self.input_tokens, self.output_tokens):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("audio provider token usage must be nonnegative")
        if type(self.provider_cleanup_failed) is not bool:
            raise TypeError("provider_cleanup_failed must be a bool")
