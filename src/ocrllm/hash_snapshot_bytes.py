"""Boundedly hash one owned image snapshot."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .errors import OCRLLMError, OutputError


_CHUNK_BYTES = 1024 * 1024


def hash_snapshot_bytes(
    snapshot_path: Path,
    *,
    maximum_byte_size: int,
) -> tuple[int, str]:
    """Return the exact size and SHA-256 of one bounded snapshot."""
    if maximum_byte_size < 1:
        raise ValueError("maximum_byte_size must be positive")

    try:
        snapshot_stream = snapshot_path.open("rb")
    except (OSError, ValueError):
        raise OutputError(
            "Validated image bytes could not be fingerprinted for resume.",
            code="OUTPUT_WRITE_FAILED",
        ) from None

    primary_error: BaseException | None = None
    try:
        digest = hashlib.sha256()
        byte_size = 0
        try:
            while True:
                remaining_bytes = maximum_byte_size - byte_size
                chunk = snapshot_stream.read(
                    min(_CHUNK_BYTES, remaining_bytes + 1)
                )
                if not chunk:
                    break
                byte_size += len(chunk)
                if byte_size > maximum_byte_size:
                    raise OutputError(
                        "Validated image bytes changed beyond their safety limit.",
                        code="OUTPUT_WRITE_FAILED",
                    ) from None
                digest.update(chunk)
        except MemoryError:
            raise OutputError(
                "Validated image bytes could not be fingerprinted within memory limits.",
                code="OUTPUT_WRITE_FAILED",
            ) from None
        except (OSError, ValueError):
            raise OutputError(
                "Validated image bytes could not be fingerprinted for resume.",
                code="OUTPUT_WRITE_FAILED",
            ) from None
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            snapshot_stream.close()
        except (OSError, ValueError):
            if primary_error is None:
                raise OutputError(
                    "Validated image bytes could not be closed after fingerprinting.",
                    code="OUTPUT_WRITE_FAILED",
                ) from None
            if isinstance(primary_error, OCRLLMError):
                primary_error._add_safe_detail(
                    "snapshot_stream_cleanup_failed",
                    True,
                )

    if byte_size == 0:
        raise OutputError(
            "Validated image bytes became empty before resume fingerprinting.",
            code="OUTPUT_WRITE_FAILED",
        ) from None
    return byte_size, digest.hexdigest()
