"""Score normalized table cells at their exact row and column coordinates."""

from __future__ import annotations

from dataclasses import dataclass

from quality_lab.normalize_content_units import normalize_visible_text
from quality_lab.parse_markdown_tables import parse_markdown_table
from quality_lab.rational_score import PERFECT_SCORE, RationalScore


_AUTOMATIC_CRITICAL_CHARACTERS = frozenset({
    "+", "-", "−", "±", "=", "≠", "<", ">", "≤", "≥", "×", "÷", "*", "/"
})
NEUTRAL_TABLE_LINE_BREAKS = ("<br>", "<br/>", "<br />")


@dataclass(frozen=True, slots=True)
class ExpectedTableCell:
    """Precommitted spellings for one table coordinate."""

    accepted: tuple[str, ...]
    case_sensitive: bool = True
    critical: bool = False

    def __post_init__(self) -> None:
        if type(self.accepted) is not tuple or not self.accepted:
            raise ValueError("table cell accepted values must be a non-empty tuple")
        if any(type(value) is not str for value in self.accepted):
            raise TypeError("table cell accepted values must be plain strings")
        if type(self.case_sensitive) is not bool or type(self.critical) is not bool:
            raise TypeError("table cell flags must be exact booleans")
        if not self.critical and any(_looks_automatically_critical(value) for value in self.accepted):
            raise ValueError(
                "table cells containing numbers, signs, relations, or operators must be critical"
            )


@dataclass(frozen=True, slots=True)
class ExpectedMarkdownTable:
    """A rectangular expected header and data grid."""

    header: tuple[ExpectedTableCell, ...]
    rows: tuple[tuple[ExpectedTableCell, ...], ...]

    def __post_init__(self) -> None:
        if type(self.header) is not tuple or not self.header:
            raise ValueError("expected table header must be a non-empty tuple")
        if type(self.rows) is not tuple or not self.rows:
            raise ValueError("expected table rows must be a non-empty tuple")
        if any(type(row) is not tuple or len(row) != len(self.header) for row in self.rows):
            raise ValueError("expected table must be rectangular")
        if any(type(cell) is not ExpectedTableCell for cell in self.header) or any(
            type(cell) is not ExpectedTableCell for row in self.rows for cell in row
        ):
            raise TypeError("expected table entries must be ExpectedTableCell values")


@dataclass(frozen=True, slots=True)
class TableScore:
    """Exact coordinate metrics and unexpected-coordinate evidence."""

    header_accuracy: RationalScore
    data_cell_accuracy: RationalScore
    critical_accuracy: RationalScore
    unexpected_coordinate_count: int
    unexpected_critical_cell_count: int = 0


def score_table_cells(expected: ExpectedMarkdownTable, recognized_markdown: str) -> TableScore:
    """Compare every header and data value only at its declared coordinate."""

    if not isinstance(expected, ExpectedMarkdownTable):
        raise TypeError("expected must be an ExpectedMarkdownTable")
    actual = parse_markdown_table(recognized_markdown)
    normalized_header = tuple(_normalized_options(cell) for cell in expected.header)
    normalized_rows = tuple(
        tuple(_normalized_options(cell) for cell in row) for row in expected.rows
    )
    header_matches = sum(
        column < len(actual.header)
        and _cell_matches(actual.header[column], options, expected.header[column])
        for column, options in enumerate(normalized_header)
    )
    data_matches = 0
    critical_matches = 0
    critical_count = 0
    unexpected_critical_cells = 0
    for row_index, row in enumerate(expected.rows):
        for column_index, cell in enumerate(row):
            if cell.critical:
                critical_count += 1
            matches = (
                row_index < len(actual.rows)
                and column_index < len(actual.rows[row_index])
                and _cell_matches(
                    actual.rows[row_index][column_index],
                    normalized_rows[row_index][column_index],
                    cell,
                )
            )
            data_matches += matches
            if cell.critical:
                critical_matches += matches
            if (
                not matches
                and row_index < len(actual.rows)
                and column_index < len(actual.rows[row_index])
                and _looks_automatically_critical(
                    actual.rows[row_index][column_index]
                )
            ):
                unexpected_critical_cells += 1

    expected_coordinates = len(expected.rows) * len(expected.header)
    actual_coordinates = len(actual.rows) * len(actual.header)
    unexpected_coordinates = sum(
        row >= len(expected.rows) or column >= len(expected.header)
        for row in range(len(actual.rows))
        for column in range(len(actual.header))
    )
    return TableScore(
        header_accuracy=RationalScore(
            header_matches, max(len(expected.header), len(actual.header))
        ),
        data_cell_accuracy=RationalScore(data_matches, expected_coordinates),
        critical_accuracy=(
            RationalScore(critical_matches, critical_count)
            if critical_count
            else PERFECT_SCORE
        ),
        unexpected_coordinate_count=max(
            unexpected_coordinates, actual_coordinates - expected_coordinates, 0
        ),
        unexpected_critical_cell_count=unexpected_critical_cells,
    )


def _normalized_options(cell: ExpectedTableCell) -> tuple[str, ...]:
    options = tuple(
        _normalize_table_cell(value, case_sensitive=cell.case_sensitive)
        for value in cell.accepted
    )
    if len(set(options)) != len(options):
        raise ValueError("table cell contains duplicate accepted values")
    return options


def _cell_matches(
    actual: str, options: tuple[str, ...], expected: ExpectedTableCell
) -> bool:
    normalized_actual = _normalize_table_cell(
        actual,
        case_sensitive=expected.case_sensitive,
    )
    return normalized_actual in options


def _normalize_table_cell(value: str, *, case_sensitive: bool = True) -> str:
    normalized_breaks = value
    for line_break in NEUTRAL_TABLE_LINE_BREAKS:
        normalized_breaks = normalized_breaks.replace(line_break, " ")
    return normalize_visible_text(
        normalized_breaks,
        case_sensitive=case_sensitive,
    )


def _looks_automatically_critical(value: str) -> bool:
    normalized = normalize_visible_text(value)
    return any(
        character.isdigit() or character in _AUTOMATIC_CRITICAL_CHARACTERS
        for character in normalized
    )
