"""Generate the synthetic formula-board fixture."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from .draw_formula_text import draw_formula_text
from .load_quality_font import load_quality_font
from .phase1_fixture_content import (
    FORMULA_ORDER_ANCHOR,
    FORMULA_TITLE,
    VISIBLE_FORMULAS,
)


FORMULA_BOARD_SIZE = (2560, 1600)


def generate_formula_board(output_path: Path) -> Path:
    """Write the deterministic dark-board formula image."""
    image = Image.new("RGB", FORMULA_BOARD_SIZE, color=(23, 59, 50))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (45, 45, 2515, 1555),
        radius=24,
        outline=(205, 191, 139),
        width=6,
    )
    draw.text(
        (110, 80),
        FORMULA_TITLE,
        font=load_quality_font(54),
        fill=(238, 235, 211),
    )
    for formula_index, (formula_id, expression) in enumerate(VISIBLE_FORMULAS):
        column = formula_index // 6
        row = formula_index % 6
        left = (120, 1360)[column]
        top = 240 + 190 * row
        draw.text(
            (left, top + 9),
            formula_id,
            font=load_quality_font(32),
            fill=(244, 192, 93),
        )
        draw_formula_text(
            draw,
            (left + 110, top),
            expression,
            fill=(244, 246, 238),
        )
        draw.line(
            (left, top + 82, left + 1050, top + 82),
            fill=(66, 112, 96),
            width=2,
        )
    draw.text(
        (1690, 1490),
        FORMULA_ORDER_ANCHOR,
        font=load_quality_font(34),
        fill=(244, 192, 93),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", compress_level=9, optimize=False)
    image.close()
    return output_path
