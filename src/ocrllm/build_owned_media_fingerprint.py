"""Build one path-bound fingerprint from already-owned media bytes."""

from __future__ import annotations

from pathlib import Path

from .contracts.source_fingerprint import SourceFingerprint
from .errors import InvalidSource, OutputError


def build_owned_media_fingerprint(
    identity_path: Path,
    *,
    byte_size: int,
    sha256: str,
) -> SourceFingerprint:
    """Bind validated byte facts to one exact canonical local path."""
    try:
        uri = identity_path.resolve(strict=True).as_uri()
    except FileNotFoundError:
        raise InvalidSource(
            "Owned media disappeared before its resume identity was built.",
            code="SOURCE_NOT_FOUND",
        ) from None
    except (OSError, ValueError):
        raise OutputError(
            "Owned media could not be bound to a resume identity.",
            code="OUTPUT_PATH_INVALID",
        ) from None
    try:
        return SourceFingerprint(uri=uri, byte_size=byte_size, sha256=sha256)
    except (TypeError, ValueError):
        raise OutputError(
            "Owned media facts could not be represented safely.",
            code="OUTPUT_WRITE_FAILED",
        ) from None
