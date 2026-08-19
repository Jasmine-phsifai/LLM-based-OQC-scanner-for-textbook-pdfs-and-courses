"""Immutable identity summary for one resumable image request."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts.source_fingerprint import SourceFingerprint


@dataclass(frozen=True, slots=True, kw_only=True)
class ImageRequestIdentity:
    """Bind ordered sources to one processor and canonical request digest."""

    request_fingerprint: str
    identity_version: str
    processor_name: str
    processor_version: str
    sources: tuple[SourceFingerprint, ...]
