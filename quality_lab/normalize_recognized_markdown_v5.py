"""Canonicalize line-leading ASCII diagram connectors in the v5 dialect."""

from __future__ import annotations

import re

from quality_lab.normalize_recognized_markdown_v4 import (
    normalize_recognized_markdown_v4,
)


_LINE_LEADING_ASCII_DIAGRAM_CONNECTOR = re.compile(
    r"^(?P<prefix> {0,3}(?:(?:(?:[-*])|(?:[0-9]{1,3}[.)]))[ \t]+)?)"
    r"->(?=[ \t]|$)[ \t]*"
)


def normalize_recognized_markdown_v5(markdown: str) -> str:
    """Remove only line-leading ASCII arrows before applying the v4 dialect."""

    if type(markdown) is not str or not markdown.strip():
        raise ValueError("recognized Markdown must be nonempty plain text")
    structural_arrows_removed = "\n".join(
        _remove_line_leading_ascii_connector(line)
        for line in markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    )
    return normalize_recognized_markdown_v4(structural_arrows_removed)


def _remove_line_leading_ascii_connector(line: str) -> str:
    match = _LINE_LEADING_ASCII_DIAGRAM_CONNECTOR.match(line)
    if match is None:
        return line
    prefix = match.group("prefix")
    return f"{prefix if prefix.strip() else ''}{line[match.end():]}"
