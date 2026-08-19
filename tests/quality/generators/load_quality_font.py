"""Validate and load the pinned Phase 1 quality font."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont


FONT_BYTES = 16_437_364
FONT_SHA256 = "2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b"


@lru_cache(maxsize=1)
def quality_font_path() -> Path:
    """Return the exact pinned font path after byte-level verification.

    The Pillow version is deliberately not gated here: rendered output is
    compared against the committed corpus by
    generate_phase1_fixtures.check_phase1_fixtures, which owns the
    environment match and the reproduction tolerance.
    """
    path = (
        Path(__file__).resolve().parents[1]
        / "assets"
        / "fonts"
        / "NotoSansCJKsc-Regular.otf"
    )
    font_bytes = path.read_bytes()
    if len(font_bytes) != FONT_BYTES:
        raise RuntimeError("the pinned quality font has an unexpected byte size")
    if hashlib.sha256(font_bytes).hexdigest() != FONT_SHA256:
        raise RuntimeError("the pinned quality font failed SHA-256 verification")
    return path


def load_quality_font(size: int) -> ImageFont.FreeTypeFont:
    """Load one size from the already verified unmodified font."""
    if type(size) is not int or size <= 0:
        raise ValueError("font size must be a positive integer")
    return ImageFont.truetype(quality_font_path(), size=size)
