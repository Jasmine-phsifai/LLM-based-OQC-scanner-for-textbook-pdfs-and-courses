"""Publish one UTF-8 text file without exposing a partial replacement."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_text_atomically(path: str | Path, text: str) -> None:
    """Write *text* to a temporary sibling, then atomically replace *path*."""
    target = Path(path)
    descriptor, temp_path = tempfile.mkstemp(
        prefix=".ocrllm-text-",
        suffix=".tmp",
        dir=target.parent,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            descriptor = -1
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())

        if target.exists():
            os.chmod(temp_path, target.stat().st_mode)
        os.replace(temp_path, target)
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.remove(temp_path)
        except OSError:
            pass
        raise
