"""Detect the canonical media type from one authorized source suffix."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from .errors import UnsupportedFormat


IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg"})
AUDIO_EXTENSIONS = frozenset({".mp3"})
PDF_EXTENSIONS = frozenset({".pdf"})


def detect_source_type(source: str | Path) -> Literal["image", "pdf", "audio"]:
    """Return the canonical type for an authorized image, PDF, or short MP3 suffix.

    Detection deliberately does not touch the filesystem or inspect content.
    ``validate_source`` and ``decode_image`` own those responsibilities.
    """
    suffix = Path(source).suffix.casefold()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    if suffix in PDF_EXTENSIONS:
        return "pdf"

    if not suffix:
        message = "The recognition source has no file extension."
    else:
        message = "The recognition source extension is not supported."
    raise UnsupportedFormat(
        message,
        details={"extension": suffix or None},
    )
