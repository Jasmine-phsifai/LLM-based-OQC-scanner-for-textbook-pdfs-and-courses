"""Parse one rectangular table from a restricted GFM pipe-table dialect."""

from __future__ import annotations

import re
from dataclasses import dataclass

from quality_lab.normalize_content_units import normalize_visible_text


_SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")


@dataclass(frozen=True, slots=True)
class ParsedMarkdownTable:
    """A normalized header and zero-based rectangular data grid."""

    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


def parse_markdown_table(markdown: str) -> ParsedMarkdownTable:
    """Parse exactly one table, rejecting ragged or extended GFM syntax."""

    if type(markdown) is not str:
        raise TypeError("table markdown must be a plain string")
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if any(not line.strip() for line in lines):
        raise ValueError("blank or surrounding non-table lines are unsupported")
    if len(lines) < 3:
        raise ValueError("table requires a header, separator, and data row")
    parsed_rows = tuple(_parse_pipe_row(line, index + 1) for index, line in enumerate(lines))
    column_count = len(parsed_rows[0])
    if column_count == 0:
        raise ValueError("table must contain at least one column")
    for row_index, row in enumerate(parsed_rows, 1):
        if len(row) != column_count:
            raise ValueError(f"ragged table row {row_index}")
    if not all(_SEPARATOR_CELL.fullmatch(cell) for cell in parsed_rows[1]):
        raise ValueError("second table row must contain only GFM separators")
    return ParsedMarkdownTable(parsed_rows[0], parsed_rows[2:])


def _parse_pipe_row(line: str, line_number: int) -> tuple[str, ...]:
    stripped = line.strip()
    if "\\|" in stripped:
        raise ValueError("escaped or embedded pipes are unsupported")
    if "|" not in stripped:
        raise ValueError(f"table line {line_number} has no pipe delimiter")
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    cells = stripped.split("|")
    return tuple(normalize_visible_text(cell) for cell in cells)
