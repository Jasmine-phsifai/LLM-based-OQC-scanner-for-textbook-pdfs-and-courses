"""Generate the synthetic bilingual calibration-table fixture."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from .load_quality_font import load_quality_font
from .phase1_fixture_content import TABLE_HEADERS, TABLE_ROWS, TABLE_TITLE


TABLE_IMAGE_SIZE = (2560, 1440)
TABLE_ORIGIN = (120, 220)
COLUMN_WIDTHS = (280, 430, 450, 430, 360, 370)
HEADER_HEIGHT = 150
ROW_HEIGHT = 180


def generate_calibration_table(output_path: Path) -> Path:
    """Write the deterministic coordinate-addressable table image."""
    image = Image.new("RGB", TABLE_IMAGE_SIZE, color=(246, 247, 243))
    draw = ImageDraw.Draw(image)
    draw.text(
        (120, 65),
        TABLE_TITLE,
        font=load_quality_font(58),
        fill=(35, 57, 73),
    )

    x_edges = [TABLE_ORIGIN[0]]
    for width in COLUMN_WIDTHS:
        x_edges.append(x_edges[-1] + width)
    y_edges = [TABLE_ORIGIN[1], TABLE_ORIGIN[1] + HEADER_HEIGHT]
    for _ in TABLE_ROWS:
        y_edges.append(y_edges[-1] + ROW_HEIGHT)

    draw.rectangle(
        (x_edges[0], y_edges[0], x_edges[-1], y_edges[1]),
        fill=(44, 78, 104),
    )
    for row_index in range(len(TABLE_ROWS)):
        fill = (255, 255, 255) if row_index % 2 == 0 else (230, 238, 241)
        draw.rectangle(
            (x_edges[0], y_edges[row_index + 1], x_edges[-1], y_edges[row_index + 2]),
            fill=fill,
        )

    for x in x_edges:
        draw.line((x, y_edges[0], x, y_edges[-1]), fill=(57, 72, 82), width=4)
    for y in y_edges:
        draw.line((x_edges[0], y, x_edges[-1], y), fill=(57, 72, 82), width=4)

    header_font = load_quality_font(30)
    cell_font = load_quality_font(36)
    for column, header_lines in enumerate(TABLE_HEADERS):
        _draw_centered_multiline(
            draw,
            "\n".join(header_lines),
            (x_edges[column], y_edges[0], x_edges[column + 1], y_edges[1]),
            font=header_font,
            fill=(255, 255, 255),
        )
    for row, row_values in enumerate(TABLE_ROWS):
        for column, value in enumerate(row_values):
            fill = (148, 53, 42) if value in {"CHECK", "HOLD"} else (29, 39, 46)
            _draw_centered_text(
                draw,
                value,
                (
                    x_edges[column],
                    y_edges[row + 1],
                    x_edges[column + 1],
                    y_edges[row + 2],
                ),
                font=cell_font,
                fill=fill,
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", compress_level=9, optimize=False)
    image.close()
    return output_path


def _draw_centered_text(draw, text, box, *, font, fill) -> None:
    bounds = draw.textbbox((0, 0), text, font=font)
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    x = box[0] + (box[2] - box[0] - width) / 2 - bounds[0]
    y = box[1] + (box[3] - box[1] - height) / 2 - bounds[1]
    draw.text((x, y), text, font=font, fill=fill)


def _draw_centered_multiline(draw, text, box, *, font, fill) -> None:
    bounds = draw.multiline_textbbox((0, 0), text, font=font, spacing=8, align="center")
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    x = box[0] + (box[2] - box[0] - width) / 2 - bounds[0]
    y = box[1] + (box[3] - box[1] - height) / 2 - bounds[1]
    draw.multiline_text(
        (x, y),
        text,
        font=font,
        fill=fill,
        spacing=8,
        align="center",
    )
