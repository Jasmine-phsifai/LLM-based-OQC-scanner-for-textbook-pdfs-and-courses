"""Hash the exact validated image bytes used by a resumable request."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .contracts.source_fingerprint import SourceFingerprint
from .errors import InvalidSource, OutputError
from .hash_snapshot_bytes import hash_snapshot_bytes
from .image_group_limits import MAX_AGGREGATE_SOURCE_BYTES
from .validate_source import MAX_SOURCE_BYTES


def fingerprint_image_sources(
    source_paths: Sequence[Path],
    snapshot_paths: Sequence[Path],
) -> tuple[SourceFingerprint, ...]:
    """Return ordered original URIs with hashes of their validated snapshots."""
    if len(source_paths) != len(snapshot_paths) or not source_paths:
        raise ValueError("source and snapshot groups must be nonempty and aligned")
    fingerprints = []
    aggregate_byte_size = 0
    for source_path, snapshot_path in zip(source_paths, snapshot_paths, strict=True):
        remaining_group_bytes = MAX_AGGREGATE_SOURCE_BYTES - aggregate_byte_size
        if remaining_group_bytes < 1:
            raise OutputError(
                "Validated image bytes changed beyond their aggregate safety limit.",
                code="OUTPUT_WRITE_FAILED",
            ) from None
        byte_size, sha256 = hash_snapshot_bytes(
            snapshot_path,
            maximum_byte_size=min(MAX_SOURCE_BYTES, remaining_group_bytes),
        )
        aggregate_byte_size += byte_size
        try:
            source_uri = source_path.resolve(strict=True).as_uri()
        except FileNotFoundError:
            raise InvalidSource(
                "A recognition source disappeared before resume identity was built.",
                code="SOURCE_NOT_FOUND",
            ) from None
        except (OSError, ValueError):
            raise OutputError(
                "Validated image bytes could not be fingerprinted for resume.",
                code="OUTPUT_WRITE_FAILED",
            ) from None
        fingerprints.append(
            SourceFingerprint(
                uri=source_uri,
                byte_size=byte_size,
                sha256=sha256,
            )
        )
    return tuple(fingerprints)
