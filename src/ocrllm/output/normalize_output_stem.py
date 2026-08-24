"""Normalize one source stem for a portable output filename."""

from __future__ import annotations

import unicodedata


WINDOWS_FORBIDDEN = frozenset('<>:"/\\|?*')
_MAX_WINDOWS_UNITS = 96


def normalize_output_stem(stem: str) -> str:
    """Return a Windows-safe NFC filename stem capped at 96 UTF-16 units."""
    normalized = unicodedata.normalize("NFC", stem)
    safe = "".join(
        "_"
        if ord(character) < 32 or ord(character) == 127 or character in WINDOWS_FORBIDDEN
        else character
        for character in normalized
    )
    safe = safe.rstrip(" .")
    kept: list[str] = []
    used_units = 0
    for character in safe:
        character_units = 2 if ord(character) > 0xFFFF else 1
        if used_units + character_units > _MAX_WINDOWS_UNITS:
            break
        kept.append(character)
        used_units += character_units
    return "".join(kept).rstrip(" .") or "source"
