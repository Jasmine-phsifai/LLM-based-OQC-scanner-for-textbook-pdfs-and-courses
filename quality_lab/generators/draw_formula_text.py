"""Draw formula text with explicit subscript and superscript placement."""

from __future__ import annotations

from PIL import ImageDraw

from .load_quality_font import load_quality_font


_SUBSCRIPT_BASE = str.maketrans("₀₁₂₃₄₅₆₇₈₉ₙ", "0123456789n")
_SUPERSCRIPT_BASE = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ", "0123456789n")
_SUBSCRIPT_CHARACTERS = frozenset("₀₁₂₃₄₅₆₇₈₉ₙ")
_SUPERSCRIPT_CHARACTERS = frozenset("⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ")


def draw_formula_text(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    *,
    fill: tuple[int, int, int],
) -> None:
    """Render supported script code points without relying on font glyphs."""
    base_font = load_quality_font(50)
    script_font = load_quality_font(34)
    cursor_x = float(position[0])
    base_y = position[1]
    for character in text:
        if character in _SUBSCRIPT_CHARACTERS:
            visible = character.translate(_SUBSCRIPT_BASE)
            draw.text(
                (cursor_x, base_y + 25),
                visible,
                font=script_font,
                fill=fill,
            )
            cursor_x += draw.textlength(visible, font=script_font)
        elif character in _SUPERSCRIPT_CHARACTERS:
            visible = character.translate(_SUPERSCRIPT_BASE)
            draw.text(
                (cursor_x, base_y - 8),
                visible,
                font=script_font,
                fill=fill,
            )
            cursor_x += draw.textlength(visible, font=script_font)
        else:
            draw.text((cursor_x, base_y), character, font=base_font, fill=fill)
            cursor_x += draw.textlength(character, font=base_font)
