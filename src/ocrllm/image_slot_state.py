"""Immutable record of one completed and persisted image workflow pass."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True, kw_only=True)
class ImageSlotState:
    """Bind one paid provider call's validated output to its slot and model."""

    slot_id: str
    workflow_pass: str
    provider: str | None
    model: str | None
    markdown: str
    markdown_sha256: str
    provider_calls_attempted: int

    def __post_init__(self) -> None:
        if type(self.slot_id) is not str or not self.slot_id:
            raise ValueError("image resume slot id is invalid")
        if type(self.workflow_pass) is not str or not self.workflow_pass:
            raise ValueError("image resume slot workflow pass is invalid")
        for value, field_name in (
            (self.provider, "provider"),
            (self.model, "model"),
        ):
            if value is not None and (type(value) is not str or not value):
                raise ValueError(f"image resume slot {field_name} is invalid")
        if type(self.markdown) is not str or not self.markdown.strip():
            raise ValueError("image resume slot Markdown is invalid")
        if type(self.markdown_sha256) is not str or _SHA256.fullmatch(
            self.markdown_sha256
        ) is None:
            raise ValueError("image resume slot Markdown SHA-256 is invalid")
        actual_sha256 = hashlib.sha256(self.markdown.encode("utf-8")).hexdigest()
        if self.markdown_sha256 != actual_sha256:
            raise ValueError("image resume slot Markdown does not match its SHA-256")
        if type(self.provider_calls_attempted) is not int or (
            self.provider_calls_attempted < 1
        ):
            raise ValueError("image resume slot call count is invalid")
