"""Canonicalize the narrowly declared Phase 1 v2 Markdown presentations."""

from __future__ import annotations

import re


_FORMULA_LABEL = re.compile(r"^F(?:0[1-9]|[1-9][0-9])$")
_EMPHASIZED_FORMULA_LABEL = re.compile(
    r"^(?:\*\*|__)?(?P<label>F(?:0[1-9]|[1-9][0-9]))(?:\*\*|__)?$"
)
_LABELED_LINE = re.compile(
    r"^(?P<prefix> {0,3}(?:(?:[-*])|(?:[0-9]{1,3}[.)]))[ \t]+)?"
    r"(?P<label>(?:\*\*|__)?F(?:0[1-9]|[1-9][0-9])(?:\*\*|__)?)"
    r"(?P<colon>[ \t]*:)?[ \t]+(?P<payload>.+?)\s*$"
)
_PAIRED_FORMULA_ROW = re.compile(
    r"^\|\s*(?P<label_one>(?:\*\*|__)?F(?:0[1-9]|[1-9][0-9])(?:\*\*|__)?)"
    r"\s*\|\s*(?P<formula_one>\$\$[^$]+\$\$|\$[^$]+\$|\\\(.*?\\\)|\\\[.*?\\\])"
    r"\s*\|\s*(?P<label_two>(?:\*\*|__)?F(?:0[1-9]|[1-9][0-9])(?:\*\*|__)?)"
    r"\s*\|\s*(?P<formula_two>\$\$[^$]+\$\$|\$[^$]+\$|\\\(.*?\\\)|\\\[.*?\\\])"
    r"\s*\|\s*$"
)
_TABLE_SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")
_FORMULA_HEADERS = ("id", "formula", "id", "formula")
_LATEX_RELATIONS = (
    ("geqslant", "≥"),
    ("leqslant", "≤"),
    ("geq", "≥"),
    ("leq", "≤"),
    ("ge", "≥"),
    ("le", "≤"),
)
_INLINE_RELATION_CHARACTERS = re.compile(r"[0-9\s.,%+\-−=<>≤≥]+")
_HORIZONTAL_RULE = re.compile(r"^ {0,3}(?:-{3,}|\*{3,}|_{3,})\s*$")


def normalize_recognized_markdown_v2(markdown: str) -> str:
    """Return v1-scorable Markdown for only the declared v2 equivalents."""

    if type(markdown) is not str or not markdown.strip():
        raise ValueError("recognized Markdown must be nonempty plain text")
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    normalized: list[str] = []
    index = 0
    while index < len(lines):
        paired_table = _normalize_paired_formula_table(lines, index)
        if paired_table is not None:
            canonical_lines, index = paired_table
            normalized.extend(canonical_lines)
            continue
        normalized.append(_normalize_line(lines[index]))
        index += 1
    return "\n".join(normalized)


def _normalize_line(line: str) -> str:
    if _HORIZONTAL_RULE.fullmatch(line):
        return ""
    labeled = _LABELED_LINE.fullmatch(line)
    if labeled is not None:
        payload = labeled.group("payload").strip()
        body = _unwrap_formula(payload)
        if body is not None:
            label_match = _EMPHASIZED_FORMULA_LABEL.fullmatch(labeled.group("label"))
            if label_match is None:
                raise ValueError("formula label is malformed")
            prefix = labeled.group("prefix") or ""
            return (
                f"{prefix}{label_match.group('label')}: "
                f"${_normalize_formula_body(body)}$"
            )
        if labeled.group("colon") is not None or _contains_math_delimiter(payload):
            raise ValueError("labeled formula must use one complete math wrapper")
    return _normalize_inline_relation_math(line)


def _normalize_paired_formula_table(
    lines: list[str], start: int
) -> tuple[tuple[str, ...], int] | None:
    if start + 1 >= len(lines):
        return None
    header = _split_pipe_cells(lines[start])
    separator = _split_pipe_cells(lines[start + 1])
    if len(header) != 4 or len(separator) != 4:
        return None
    header_values = tuple(cell.casefold() for cell in header)
    if header_values not in {("", "", "", ""), _FORMULA_HEADERS}:
        return None
    if not all(_TABLE_SEPARATOR_CELL.fullmatch(cell) for cell in separator):
        raise ValueError("paired formula table separator is malformed")

    canonical: list[str] = []
    labels: set[str] = set()
    index = start + 2
    while index < len(lines) and "|" in lines[index]:
        row = _PAIRED_FORMULA_ROW.fullmatch(lines[index].strip())
        if row is None:
            raise ValueError("paired formula table must contain two strict pairs per row")
        for label_group, formula_group in (
            ("label_one", "formula_one"),
            ("label_two", "formula_two"),
        ):
            label_match = _EMPHASIZED_FORMULA_LABEL.fullmatch(row.group(label_group))
            body = _unwrap_formula(row.group(formula_group))
            if label_match is None or body is None:
                raise ValueError("paired formula table contains a malformed pair")
            label = label_match.group("label")
            if label in labels:
                raise ValueError(f"duplicate formula label: {label}")
            labels.add(label)
            canonical.append(f"{label}: ${_normalize_formula_body(body)}$")
        index += 1
    if not canonical:
        raise ValueError("paired formula table must contain at least one data row")
    return tuple(canonical), index


def _split_pipe_cells(line: str) -> tuple[str, ...]:
    stripped = line.strip()
    if not stripped or "|" not in stripped:
        return ()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return tuple(cell.strip() for cell in stripped.split("|"))


def _unwrap_formula(payload: str) -> str | None:
    wrappers = (("$$", "$$"), (r"\(", r"\)"), (r"\[", r"\]"), ("$", "$"))
    for opening, closing in wrappers:
        if not payload.startswith(opening) or not payload.endswith(closing):
            continue
        body = payload[len(opening) : len(payload) - len(closing)].strip()
        if not body:
            raise ValueError("formula body must not be empty")
        if opening in {"$", "$$"} and "$" in body:
            raise ValueError("formula contains an ambiguous dollar delimiter")
        return body
    return None


def _normalize_formula_body(body: str) -> str:
    normalized = body
    for command, replacement in _LATEX_RELATIONS:
        normalized = re.sub(
            rf"\\{command}(?![A-Za-z])",
            lambda _match, value=replacement: rf"\{_visible_relation_command(value)}",
            normalized,
        )
    return normalized


def _visible_relation_command(value: str) -> str:
    return "geq" if value == "≥" else "leq"


def _normalize_inline_relation_math(line: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(line):
        if line.startswith("$$", index) or line.startswith(r"\[", index):
            raise ValueError("display math must be a standalone labeled formula")
        if line[index] == "$":
            closing = line.find("$", index + 1)
            if closing < 0:
                raise ValueError("inline math has an unclosed dollar delimiter")
            result.append(_normalize_inline_relation_body(line[index + 1 : closing]))
            index = closing + 1
            continue
        if line.startswith(r"\(", index):
            closing = line.find(r"\)", index + 2)
            if closing < 0:
                raise ValueError("inline math has an unclosed parenthesis delimiter")
            result.append(_normalize_inline_relation_body(line[index + 2 : closing]))
            index = closing + 2
            continue
        if line.startswith(r"\)", index) or line.startswith(r"\]", index):
            raise ValueError("inline math has an unmatched closing delimiter")
        result.append(line[index])
        index += 1
    return "".join(result)


def _normalize_inline_relation_body(body: str) -> str:
    normalized = body.strip()
    for command, replacement in _LATEX_RELATIONS:
        normalized = re.sub(
            rf"\\{command}(?![A-Za-z])",
            replacement,
            normalized,
        )
    normalized = normalized.replace(r"\%", "%")
    if (
        not normalized
        or _INLINE_RELATION_CHARACTERS.fullmatch(normalized) is None
        or not any(relation in normalized for relation in ("=", "<", ">", "≤", "≥"))
    ):
        raise ValueError("inline math is outside the declared relation-only dialect")
    return normalized


def _contains_math_delimiter(value: str) -> bool:
    return any(marker in value for marker in ("$", r"\(", r"\)", r"\[", r"\]"))
