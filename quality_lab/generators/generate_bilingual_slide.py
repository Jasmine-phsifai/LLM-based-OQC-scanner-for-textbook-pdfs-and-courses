"""Generate the clean bilingual printed-slide fixture."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from .load_quality_font import load_quality_font
from .phase1_fixture_content import (
    SLIDE_CARDS,
    SLIDE_ORDER_ANCHOR,
    SLIDE_SUBTITLE,
    SLIDE_TITLE,
)


SLIDE_SIZE = (2560, 1440)


def generate_bilingual_slide(output_path: Path) -> Path:
    """Write the deterministic clean slide and return its path."""
    image = Image.new("RGB", SLIDE_SIZE, color=(239, 244, 249))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((60, 40, 2500, 190), radius=28, fill=(27, 55, 83))
    draw.text(
        (96, 62),
        SLIDE_TITLE,
        font=load_quality_font(58),
        fill=(255, 255, 255),
    )
    draw.text(
        (1630, 82),
        SLIDE_SUBTITLE,
        font=load_quality_font(42),
        fill=(216, 234, 248),
    )

    card_x_positions = (96, 1304)
    card_y_positions = (230, 492, 754, 1016)
    for card_index, card_lines in enumerate(SLIDE_CARDS):
        column = card_index % 2
        row = card_index // 2
        left = card_x_positions[column]
        top = card_y_positions[row]
        draw.rounded_rectangle(
            (left, top, left + 1160, top + 238),
            radius=22,
            fill=(255, 255, 255),
            outline=(170, 187, 202),
            width=3,
        )
        draw.text(
            (left + 26, top + 14),
            card_lines[0],
            font=load_quality_font(31),
            fill=(23, 68, 105),
        )
        for line_index, line in enumerate(card_lines[1:5]):
            draw.text(
                (left + 28, top + 59 + 33 * line_index),
                line,
                font=load_quality_font(27),
                fill=(31, 42, 51),
            )
        draw.text(
            (left + 28, top + 194),
            card_lines[5],
            font=load_quality_font(28),
            fill=(151, 54, 36),
        )

    draw.text(
        (96, 1328),
        SLIDE_ORDER_ANCHOR,
        font=load_quality_font(34),
        fill=(71, 36, 148),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", compress_level=9, optimize=False)
    image.close()
    return output_path
