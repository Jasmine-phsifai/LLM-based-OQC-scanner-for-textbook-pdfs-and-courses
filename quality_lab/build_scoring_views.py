"""Build deterministic text, formula, table, and anchor views from Markdown."""

from __future__ import annotations

import re
from dataclasses import dataclass


_ALLOWED_NEUTRAL_MARKDOWN = frozenset(
    {
        "headings",
        "unordered_list_markers",
        "ordered_list_markers",
        "emphasis",
        "formula_delimiters",
        "table_delimiters",
    }
)
_HEADING_PREFIX = re.compile(r"^ {0,3}#{1,6}[ \t]+")
_UNORDERED_LIST_PREFIX = re.compile(r"^ {0,3}[-*][ \t]+")
_ORDERED_LIST_PREFIX = re.compile(r"^ {0,3}[0-9]{1,3}[.)][ \t]+")
_FORMULA_LABEL_PREFIX = re.compile(r"^F[0-9]{2}\s*:")
_LABELED_DOLLAR_FORMULA = re.compile(
    r"^(?P<label>[A-Z][A-Z0-9_-]{0,31})\s*:\s*\$(?P<body>[^$]+)\$\s*$"
)
_LABELED_DOUBLE_DOLLAR_FORMULA = re.compile(
    r"^(?P<label>[A-Z][A-Z0-9_-]{0,31})\s*:\s*\$\$(?P<body>.+?)\$\$\s*$"
)
_LABELED_PAREN_FORMULA = re.compile(
    r"^(?P<label>[A-Z][A-Z0-9_-]{0,31})\s*:\s*\\\((?P<body>.*?)\\\)\s*$"
)
_LABELED_BRACKET_FORMULA = re.compile(
    r"^(?P<label>[A-Z][A-Z0-9_-]{0,31})\s*:\s*\\\[(?P<body>.*?)\\\]\s*$"
)
_LABELED_PIPE_FORMULA = re.compile(
    r"^\|?\s*(?P<label>F[0-9]{2})\s*\|\s*(?P<payload>.+?)\s*\|?$"
)
_TABLE_SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")
_EMPHASIS_SPAN = re.compile(r"(?P<marker>\*\*|__)(?P<body>\S(?:.*?\S)?)\1")
_MATH_DELIMITER_PAIRS = (
    ("$$", "$$"),
    (r"\(", r"\)"),
    (r"\[", r"\]"),
    ("$", "$"),
)
_FORMULA_TABLE_FIRST_HEADERS = frozenset({"id", "label", "formula id", "编号", "标签"})
_FORMULA_TABLE_SECOND_HEADERS = frozenset(
    {"formula", "expression", "equation", "公式", "表达式", "方程"}
)


@dataclass(frozen=True, slots=True)
class ScoringViews:
    """Channel-specific content after removing only frozen neutral Markdown."""

    text: str
    formulas: str
    table: str | None
    anchors: str


def build_scoring_views(
    markdown: str,
    *,
    neutral_markdown: tuple[str, ...],
) -> ScoringViews:
    """Return isolated scoring views or reject unsupported/ambiguous structure."""

    if type(markdown) is not str or not markdown.strip():
        raise ValueError("recognized Markdown must be nonempty plain text")
    if type(neutral_markdown) is not tuple:
        raise TypeError("neutral_markdown must be a tuple")
    if len(set(neutral_markdown)) != len(neutral_markdown):
        raise ValueError("neutral_markdown must not contain duplicates")
    unknown = set(neutral_markdown) - _ALLOWED_NEUTRAL_MARKDOWN
    if unknown:
        raise ValueError(f"unsupported neutral Markdown rule: {sorted(unknown)[0]}")

    rules = frozenset(neutral_markdown)
    normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
    lines = tuple(_strip_line_scaffolding(line, rules=rules) for line in normalized.split("\n"))

    canonical_formula_by_index: dict[int, str] = {}
    if "formula_delimiters" in rules:
        canonical_formula_by_index = {
            index: canonical
            for index, line in enumerate(lines)
            if (canonical := _canonical_formula_line(line)) is not None
        }
    formula_scaffolding_indexes = _formula_table_scaffolding_indexes(
        lines,
        formula_indexes=frozenset(canonical_formula_by_index),
    )
    table_input = tuple(
        ""
        if index in canonical_formula_by_index or index in formula_scaffolding_indexes
        else line
        for index, line in enumerate(lines)
    )
    table_indexes, table = _extract_table(
        table_input,
        enabled="table_delimiters" in rules,
    )

    text_lines: list[str] = []
    formula_lines: list[str] = []
    for index, line in enumerate(lines):
        if index in canonical_formula_by_index:
            formula_lines.append(canonical_formula_by_index[index])
            continue
        if index in formula_scaffolding_indexes:
            continue
        if index in table_indexes:
            continue
        if "formula_delimiters" in rules:
            if _looks_like_malformed_formula(line):
                raise ValueError(f"malformed labeled formula on line {index + 1}")
        text_lines.append(line)

    visible_text = _join_nonempty_lines(text_lines)
    return ScoringViews(
        text=visible_text,
        formulas="\n".join(formula_lines),
        table=table,
        anchors=visible_text,
    )


def _strip_line_scaffolding(line: str, *, rules: frozenset[str]) -> str:
    stripped = line.rstrip()
    if "headings" in rules:
        stripped = _HEADING_PREFIX.sub("", stripped)
    if "unordered_list_markers" in rules:
        stripped = _UNORDERED_LIST_PREFIX.sub("", stripped)
    if "ordered_list_markers" in rules:
        stripped = _ORDERED_LIST_PREFIX.sub("", stripped)
    if "emphasis" in rules:
        stripped = _remove_emphasis_outside_math(stripped)
    return stripped.strip()


def _remove_emphasis_outside_math(value: str) -> str:
    """Remove balanced emphasis only from regions outside complete math spans."""

    result: list[str] = []
    outside_start = 0
    index = 0
    while index < len(value):
        delimiters = _math_delimiters_at(value, index)
        if delimiters is None:
            index += 1
            continue
        opening, closing = delimiters
        closing_index = value.find(closing, index + len(opening))
        if closing_index < 0:
            break
        result.append(_remove_balanced_emphasis(value[outside_start:index]))
        math_end = closing_index + len(closing)
        result.append(value[index:math_end])
        index = math_end
        outside_start = math_end
    result.append(_remove_balanced_emphasis(value[outside_start:]))
    return "".join(result)


def _remove_balanced_emphasis(value: str) -> str:
    stripped = value
    while True:
        stripped, substitutions = _EMPHASIS_SPAN.subn(
            lambda match: match.group("body"),
            stripped,
        )
        if not substitutions:
            break
    if "**" in stripped or "__" in stripped:
        raise ValueError("unbalanced or ambiguous emphasis markers")
    return stripped


def _math_delimiters_at(value: str, index: int) -> tuple[str, str] | None:
    return next(
        (
            (opening, closing)
            for opening, closing in _MATH_DELIMITER_PAIRS
            if value.startswith(opening, index)
        ),
        None,
    )


def _canonical_formula_line(line: str) -> str | None:
    if not line:
        return None
    pipe_match = _LABELED_PIPE_FORMULA.fullmatch(line)
    if pipe_match is not None:
        body = _formula_payload_body(pipe_match.group("payload"))
        if body is None:
            return None
        return f'{pipe_match.group("label")}: ${body}$'
    for pattern in (
        _LABELED_DOUBLE_DOLLAR_FORMULA,
        _LABELED_DOLLAR_FORMULA,
        _LABELED_PAREN_FORMULA,
        _LABELED_BRACKET_FORMULA,
    ):
        match = pattern.fullmatch(line)
        if match is not None:
            body = match.group("body").strip()
            if not body:
                raise ValueError("formula body must not be empty")
            return f'{match.group("label")}: ${body}$'
    return None


def _formula_payload_body(payload: str) -> str | None:
    stripped = payload.strip()
    wrappers = (("$$", "$$"), ("$", "$"), (r"\(", r"\)"), (r"\[", r"\]"))
    for opening, closing in wrappers:
        if stripped.startswith(opening) and stripped.endswith(closing):
            body = stripped[len(opening) : len(stripped) - len(closing)].strip()
            return body or None
    return None


def _formula_table_scaffolding_indexes(
    lines: tuple[str, ...],
    *,
    formula_indexes: frozenset[int],
) -> frozenset[int]:
    scaffolding: set[int] = set()
    for index in sorted(formula_indexes):
        if _LABELED_PIPE_FORMULA.fullmatch(lines[index]) is None or index < 2:
            continue
        if not _is_separator_row(lines[index - 1]):
            continue
        if not _is_formula_table_header(lines[index - 2]):
            raise ValueError("formula table has an unsupported header")
        scaffolding.update((index - 2, index - 1))
    return frozenset(scaffolding)


def _is_formula_table_header(line: str) -> bool:
    cells = _split_pipe_cells(line)
    return bool(
        len(cells) == 2
        and cells[0].casefold() in _FORMULA_TABLE_FIRST_HEADERS
        and cells[1].casefold() in _FORMULA_TABLE_SECOND_HEADERS
    )


def _looks_like_malformed_formula(line: str) -> bool:
    return bool(
        "$" in line
        or "\\(" in line
        or "\\)" in line
        or "\\[" in line
        or "\\]" in line
        or _FORMULA_LABEL_PREFIX.match(line)
    )


def _extract_table(
    lines: tuple[str, ...], *, enabled: bool
) -> tuple[frozenset[int], str | None]:
    if not enabled:
        return frozenset(), None
    blocks: list[tuple[int, int]] = []
    index = 0
    while index + 1 < len(lines):
        if _is_table_row(lines[index]) and _is_separator_row(lines[index + 1]):
            end = index + 2
            while end < len(lines) and _is_table_row(lines[end]):
                end += 1
            if end == index + 2:
                raise ValueError("table must contain at least one data row")
            blocks.append((index, end))
            index = end
            continue
        index += 1
    if len(blocks) > 1:
        raise ValueError("recognized Markdown contains more than one table")
    if not blocks:
        if any("|" in line for line in lines):
            raise ValueError("recognized Markdown contains malformed table syntax")
        return frozenset(), None
    start, end = blocks[0]
    indexes = frozenset(range(start, end))
    if any("|" in line for index, line in enumerate(lines) if index not in indexes):
        raise ValueError("recognized Markdown contains table syntax outside its table")
    return indexes, "\n".join(lines[start:end])


def _is_table_row(line: str) -> bool:
    return bool(line and "|" in line)


def _is_separator_row(line: str) -> bool:
    if not _is_table_row(line):
        return False
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    cells = tuple(cell.strip() for cell in stripped.split("|"))
    return bool(cells) and all(_TABLE_SEPARATOR_CELL.fullmatch(cell) for cell in cells)


def _split_pipe_cells(line: str) -> tuple[str, ...]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return tuple(cell.strip() for cell in stripped.split("|"))


def _join_nonempty_lines(lines: list[str]) -> str:
    return "\n".join(line for line in lines if line)
