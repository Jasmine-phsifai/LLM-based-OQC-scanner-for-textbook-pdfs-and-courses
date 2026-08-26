"""Represent one settled paid long-audio request."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Literal


_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True, kw_only=True)
class LongAudioSettledSlot:
    """Keep one reusable transcript with honest call and usage facts."""

    window_index: int
    request_fingerprint: str
    markdown: str
    markdown_sha256: str
    provider: str
    model: str
    transport: str
    provider_calls_attempted: int
    input_tokens: int | None
    output_tokens: int | None
    status: Literal["complete", "partial"]
    warnings: tuple[str, ...]
    provider_file_cleanup_succeeded: bool | None
    provider_client_cleanup_succeeded: bool | None

    def __post_init__(self) -> None:
        if type(self.window_index) is not int or self.window_index < 0:
            raise ValueError("long-audio slot window index is invalid") from None
        if (
            type(self.request_fingerprint) is not str
            or _SHA256.fullmatch(self.request_fingerprint) is None
        ):
            raise ValueError("long-audio slot request fingerprint is invalid") from None
        if type(self.markdown) is not str or not self.markdown.strip():
            raise ValueError("long-audio slot Markdown is invalid") from None
        if (
            type(self.markdown_sha256) is not str
            or _SHA256.fullmatch(self.markdown_sha256) is None
            or self.markdown_sha256
            != hashlib.sha256(self.markdown.encode("utf-8")).hexdigest()
        ):
            raise ValueError("long-audio slot Markdown digest is invalid") from None
        for field_name, value in (
            ("provider", self.provider),
            ("model", self.model),
            ("transport", self.transport),
        ):
            if type(value) is not str or not value or value != value.strip():
                raise ValueError(f"long-audio slot {field_name} is invalid") from None
        if (
            type(self.provider_calls_attempted) is not int
            or self.provider_calls_attempted < 1
        ):
            raise ValueError("long-audio slot call count is invalid") from None
        for field_name, value in (
            ("input token usage", self.input_tokens),
            ("output token usage", self.output_tokens),
        ):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"long-audio slot {field_name} is invalid") from None
        if self.status not in ("complete", "partial"):
            raise ValueError("long-audio slot status is invalid") from None
        if type(self.warnings) is not tuple or any(
            type(warning) is not str or not warning.strip()
            for warning in self.warnings
        ):
            raise ValueError("long-audio slot warnings are invalid") from None
        if (self.status == "complete") != (not self.warnings):
            raise ValueError(
                "long-audio slot status and warnings are inconsistent"
            ) from None
        for field_name, value in (
            ("provider file cleanup", self.provider_file_cleanup_succeeded),
            ("provider client cleanup", self.provider_client_cleanup_succeeded),
        ):
            if value is not None and type(value) is not bool:
                raise ValueError(f"long-audio slot {field_name} is invalid") from None
