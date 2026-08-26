"""Recover one platform path from a validated source fingerprint."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .contracts.source_fingerprint import SourceFingerprint
from .errors import ResumeStateError


def source_fingerprint_path(source: SourceFingerprint) -> Path:
    """Return an absolute local path or reject ambiguous saved identity."""
    try:
        parsed = urlsplit(source.uri)
        decoded = unquote(parsed.path, errors="strict")
    except (TypeError, ValueError, UnicodeDecodeError):
        raise _invalid() from None
    if (
        parsed.scheme != "file"
        or parsed.query
        or parsed.fragment
        or "\x00" in decoded
        or "\\" in decoded
    ):
        raise _invalid()
    if os.name == "nt":
        if parsed.netloc:
            path = Path(f"//{parsed.netloc}{decoded}")
        else:
            path = Path(
                decoded[1:]
                if len(decoded) >= 3
                and decoded[0] == "/"
                and decoded[1].isalpha()
                and decoded[2] == ":"
                else decoded
            )
    else:
        if parsed.netloc not in {"", "localhost"}:
            raise _invalid()
        path = Path(decoded)
    if not path.is_absolute():
        raise _invalid()
    return path


def _invalid() -> ResumeStateError:
    return ResumeStateError(
        "Saved video media identity is not an unambiguous local path.",
        code="RESUME_STATE_INVALID",
    )
