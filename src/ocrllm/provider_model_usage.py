"""Cumulative call and token facts for one exact provider model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderModelUsage:
    """Keep cumulative trustworthy usage for one exact provider model."""

    vendor: str
    model: str
    calls: int
    input_tokens: int | None
    output_tokens: int | None

    def __post_init__(self) -> None:
        if not _is_text(self.vendor) or not _is_text(self.model):
            raise ValueError("provider-model usage identity is invalid")
        if type(self.calls) is not int or self.calls < 1:
            raise ValueError("provider-model usage calls are invalid")
        for value in (self.input_tokens, self.output_tokens):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("provider-model token usage is invalid")


def _is_text(value: object) -> bool:
    return type(value) is str and bool(value.strip())
