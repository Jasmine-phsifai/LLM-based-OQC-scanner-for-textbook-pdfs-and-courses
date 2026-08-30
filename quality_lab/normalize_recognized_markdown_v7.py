"""Canonicalize bounded single-letter Roman groups in labeled formulas."""

from __future__ import annotations

import re

from quality_lab.normalize_recognized_markdown_v6 import (
    normalize_recognized_markdown_v6,
)


_LABELED_FORMULA_LINE = re.compile(
    r"^(?P<prefix>\s*F(?:0[1-9]|[1-9][0-9])\s*:\s*\$)"
    r"(?P<formula>.*)"
    r"(?P<suffix>\$\s*)$"
)
_SINGLE_ASCII_SYMBOL_ROMAN = re.compile(r"\\mathrm\{(?P<symbol>[A-Za-z])\}")


def normalize_recognized_markdown_v7(markdown: str) -> str:
    r"""Unwrap only one ASCII letter in ``\mathrm{}`` inside labeled formulas."""

    if type(markdown) is not str or not markdown.strip():
        raise ValueError("recognized Markdown must be nonempty plain text")
    v6_markdown = normalize_recognized_markdown_v6(markdown)
    return "\n".join(_normalize_formula_line(line) for line in v6_markdown.split("\n"))


def _normalize_formula_line(line: str) -> str:
    match = _LABELED_FORMULA_LINE.fullmatch(line)
    if match is None:
        return line
    formula = _SINGLE_ASCII_SYMBOL_ROMAN.sub(
        lambda item: item.group("symbol"),
        match.group("formula"),
    )
    return f"{match.group('prefix')}{formula}{match.group('suffix')}"
