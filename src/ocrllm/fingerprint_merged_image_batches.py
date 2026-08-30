"""Validate and fingerprint one complete merged-image plan."""

from __future__ import annotations

from pathlib import Path

from .contracts.source_fingerprint import SourceFingerprint
from .fingerprint_image_sources import fingerprint_image_sources
from .validate_image_group import validate_image_group


def fingerprint_merged_image_batches(
    batches: tuple[tuple[Path, ...], ...],
) -> tuple[SourceFingerprint, ...]:
    """Preflight every batch and hash every ordered source before dispatch."""
    fingerprints: list[SourceFingerprint] = []
    for batch in batches:
        validate_image_group(batch)
        fingerprints.extend(fingerprint_image_sources(batch, batch))
    return tuple(fingerprints)
