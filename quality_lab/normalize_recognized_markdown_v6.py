"""Canonicalize bounded single-symbol LaTeX text groups in formula lines."""

from __future__ import annotations

import re

from quality_lab.normalize_recognized_markdown_v5 import (
    normalize_recognized_markdown_v5,
)


_LABELED_FORMULA_LINE = re.compile(
    r"^(?P<prefix>\s*F(?:0[1-9]|[1-9][0-9])\s*:\s*\$)"
    r"(?P<formula>.*)"
    r"(?P<suffix>\$\s*)$"
)
_SINGLE_ASCII_SYMBOL_TEXT = re.compile(r"\\text\{(?P<symbol>[A-Za-z])\}")


def normalize_recognized_markdown_v6(markdown: str) -> str:
    """Unwrap only one ASCII letter in ``\text{}`` inside labeled formulas."""

    if type(markdown) is not str or not markdown.strip():
        raise ValueError("recognized Markdown must be nonempty plain text")
    v5_markdown = normalize_recognized_markdown_v5(markdown)
    return "\n".join(_normalize_formula_line(line) for line in v5_markdown.split("\n"))


def _normalize_formula_line(line: str) -> str:
    match = _LABELED_FORMULA_LINE.fullmatch(line)
    if match is None:
        return line
    formula = _SINGLE_ASCII_SYMBOL_TEXT.sub(
        lambda item: item.group("symbol"),
        match.group("formula"),
    )
    return f"{match.group('prefix')}{formula}{match.group('suffix')}"
