"""Structured successful response from a built-in vision adapter."""

from __future__ import annotations

from dataclasses import dataclass

from .safe_provider_request_id import safe_provider_request_id


@dataclass(frozen=True, slots=True)
class VisionProviderResponse:
    """Carry one fresh result and its local client-cleanup state."""

    markdown: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    client_closed: bool = True
    request_id: str | None = None

    def __post_init__(self) -> None:
        for value in (self.input_tokens, self.output_tokens):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("provider token usage must be nonnegative integers")
        if type(self.client_closed) is not bool:
            raise TypeError("client_closed must be a bool")
        if self.request_id != safe_provider_request_id(self.request_id):
            raise ValueError("provider request_id must be safe text or None")
