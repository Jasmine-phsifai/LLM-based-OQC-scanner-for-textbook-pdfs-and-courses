"""Aggregate one ProviderModel call across finite retries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar


_ResponseT = TypeVar("_ResponseT")


@dataclass(frozen=True, slots=True)
class ProviderModelCallResult(Generic[_ResponseT]):
    """Carry the final response and all provider work spent to obtain it."""

    response: _ResponseT = field(repr=False)
    calls: int
    failed_input_tokens: int | None
    failed_output_tokens: int | None
    prior_cleanup_failed: bool

    def __post_init__(self) -> None:
        if type(self.calls) is not int or self.calls < 1:
            raise ValueError("provider-model call count must be positive")
        for value in (self.failed_input_tokens, self.failed_output_tokens):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("failed retry token usage must be nonnegative")
        if type(self.prior_cleanup_failed) is not bool:
            raise TypeError("prior_cleanup_failed must be a bool")
