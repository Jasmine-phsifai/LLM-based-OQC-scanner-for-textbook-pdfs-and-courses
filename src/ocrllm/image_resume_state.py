"""Immutable completed-or-partial state for one resumable image group."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from .contracts.source_fingerprint import SourceFingerprint
from .freeze_json_value import JSONValue, freeze_json_value
from .image_slot_state import ImageSlotState


IMAGE_RESUME_STATE_VERSION = "ocrllm.image-resume.v2"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True, kw_only=True)
class ImageResumeState:
    """Store completed workflow slots plus the final output once assembled.

    A state with empty ``markdown`` is an incomplete checkpoint: it holds the
    workflow slots paid for so far and no final result. A state with nonempty
    ``markdown`` is complete and must carry its final digest.
    """

    state_version: str
    identity_version: str
    request_fingerprint: str
    processor_name: str
    processor_version: str
    sources: tuple[SourceFingerprint, ...]
    markdown: str
    media_type: str
    profile: str
    status: str
    hotwords: tuple[str, ...]
    warnings: tuple[str, ...]
    metadata: Mapping[str, JSONValue] = field(default_factory=dict)
    slots: tuple[ImageSlotState, ...] = ()
    final_markdown_sha256: str = ""

    def __post_init__(self) -> None:
        if self.state_version != IMAGE_RESUME_STATE_VERSION:
            raise ValueError("image resume state version is unsupported")
        if type(self.identity_version) is not str or not self.identity_version:
            raise ValueError("image resume identity version is invalid")
        if type(self.request_fingerprint) is not str or _SHA256.fullmatch(
            self.request_fingerprint
        ) is None:
            raise ValueError("image resume request fingerprint is invalid")
        if type(self.processor_name) is not str or not self.processor_name:
            raise ValueError("image resume processor name is invalid")
        if type(self.processor_version) is not str or not self.processor_version:
            raise ValueError("image resume processor version is invalid")
        if (
            type(self.sources) is not tuple
            or not self.sources
            or any(type(source) is not SourceFingerprint for source in self.sources)
        ):
            raise ValueError("image resume sources are invalid")
        if type(self.markdown) is not str:
            raise ValueError("image resume Markdown is invalid")
        if self.markdown:
            if not self.markdown.strip():
                raise ValueError("image resume Markdown is invalid")
            if type(self.final_markdown_sha256) is not str or _SHA256.fullmatch(
                self.final_markdown_sha256
            ) is None:
                raise ValueError("image resume final Markdown SHA-256 is invalid")
        else:
            if self.status != "partial" or self.final_markdown_sha256 != "":
                raise ValueError(
                    "an incomplete image resume checkpoint must be partial "
                    "and carry no final digest"
                )
        if self.media_type != "image":
            raise ValueError("image resume media type is invalid")
        if type(self.profile) is not str or not self.profile:
            raise ValueError("image resume profile is invalid")
        if self.status not in {"complete", "partial"}:
            raise ValueError("image resume status is invalid")
        if type(self.hotwords) is not tuple or any(
            type(value) is not str for value in self.hotwords
        ):
            raise ValueError("image resume hotwords are invalid")
        if type(self.warnings) is not tuple or any(
            type(value) is not str for value in self.warnings
        ):
            raise ValueError("image resume warnings are invalid")
        if type(self.slots) is not tuple or any(
            type(slot) is not ImageSlotState for slot in self.slots
        ):
            raise ValueError("image resume slots are invalid")
        slot_ids = [slot.slot_id for slot in self.slots]
        if len(set(slot_ids)) != len(slot_ids):
            raise ValueError("image resume slot ids are duplicated")
        frozen_metadata = freeze_json_value(self.metadata)
        if not isinstance(frozen_metadata, MappingProxyType):
            raise ValueError("image resume metadata is invalid")
        object.__setattr__(self, "metadata", frozen_metadata)
