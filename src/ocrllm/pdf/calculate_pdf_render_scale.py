"""Calculate one bounded PDF page render scale."""

from __future__ import annotations

import math

from ..errors import PDFError


PDF_RENDER_DPI = 200
MAX_RENDERED_SIDE = 4096
MAX_RENDERED_PAGE_PIXELS = 16_777_216


def calculate_pdf_render_scale(
    width_points: float,
    height_points: float,
    *,
    maximum_pixels: int = MAX_RENDERED_PAGE_PIXELS,
) -> float:
    """Fit one PDF page within DPI, side, and pixel ceilings."""
    if (
        not isinstance(width_points, (int, float))
        or not isinstance(height_points, (int, float))
        or not math.isfinite(float(width_points))
        or not math.isfinite(float(height_points))
        or width_points <= 0
        or height_points <= 0
        or type(maximum_pixels) is not int
        or maximum_pixels <= 0
    ):
        raise PDFError(
            "A PDF page has invalid render dimensions.",
            code="PDF_INVALID",
        ) from None
    return min(
        PDF_RENDER_DPI / 72,
        MAX_RENDERED_SIDE / max(width_points, height_points),
        math.sqrt(maximum_pixels / (width_points * height_points)),
    )
