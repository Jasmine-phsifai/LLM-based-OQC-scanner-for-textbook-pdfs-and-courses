"""Hash one request-owned video snapshot without loading it into memory."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

from .errors import OCRLLMError, OutputError


def hash_video_snapshot(snapshot_path: Path) -> tuple[int, str]:
    """Return exact size and SHA-256 for stable request-owned bytes."""
    stream = None
    primary_error: BaseException | None = None
    try:
        stream = snapshot_path.open("rb")
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or opened.st_size <= 0:
            raise OutputError(
                "The owned video snapshot is not a nonempty regular file.",
                code="OUTPUT_WRITE_FAILED",
            ) from None
        digest = hashlib.sha256()
        read_size = 0
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            read_size += len(chunk)
            digest.update(chunk)
        if read_size != opened.st_size:
            raise OutputError(
                "The owned video snapshot changed while it was fingerprinted.",
                code="OUTPUT_WRITE_FAILED",
            ) from None
        return read_size, digest.hexdigest()
    except BaseException as error:
        primary_error = error
        if isinstance(error, OutputError):
            raise
        if isinstance(error, (OSError, ValueError, MemoryError)):
            raise OutputError(
                "The owned video snapshot could not be fingerprinted safely.",
                code="OUTPUT_WRITE_FAILED",
            ) from None
        raise
    finally:
        if stream is not None:
            try:
                stream.close()
            except (OSError, ValueError):
                if primary_error is None:
                    raise OutputError(
                        "The owned video snapshot could not be closed safely.",
                        code="OUTPUT_WRITE_FAILED",
                    ) from None
                if isinstance(primary_error, OCRLLMError):
                    primary_error._add_safe_detail("snapshot_stream_cleanup_failed", True)
