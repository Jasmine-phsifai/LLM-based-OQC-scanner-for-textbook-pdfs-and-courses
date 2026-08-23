"""Verify owned image snapshots against a request identity."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .contracts.source_fingerprint import SourceFingerprint
from .errors import OutputError
from .hash_snapshot_bytes import hash_snapshot_bytes


def verify_image_snapshots(
    snapshot_paths: Sequence[Path],
    expected_sources: Sequence[SourceFingerprint],
) -> None:
    """Reject snapshots that no longer match their recorded identity."""
    if len(snapshot_paths) != len(expected_sources) or not snapshot_paths:
        raise OutputError(
            "Validated image snapshots no longer match the resume request.",
            code="OUTPUT_WRITE_FAILED",
        ) from None

    for snapshot_path, expected in zip(
        snapshot_paths,
        expected_sources,
        strict=True,
    ):
        byte_size, sha256 = hash_snapshot_bytes(
            snapshot_path,
            maximum_byte_size=expected.byte_size,
        )
        if byte_size != expected.byte_size or sha256 != expected.sha256:
            raise OutputError(
                "Validated image bytes changed before checkpoint persistence.",
                code="OUTPUT_WRITE_FAILED",
            ) from None
