"""Canonicalize source-layout arrows in the Phase 1 v4 dialect."""

from __future__ import annotations

import re

from quality_lab.normalize_recognized_markdown_v3 import (
    normalize_recognized_markdown_v3,
)


_LINE_LEADING_DIAGRAM_CONNECTOR = re.compile(
    r"^(?P<prefix> {0,3}(?:(?:(?:[-*])|(?:[0-9]{1,3}[.)]))[ \t]+)?)"
    r"(?:\$(?:\\rightarrow|\\downarrow)\$|\\(?:rightarrow|downarrow)|[→↓])"
    r"(?=[ \t]|$)[ \t]*"
)


def normalize_recognized_markdown_v4(markdown: str) -> str:
    """Remove only line-leading diagram connectors, including LaTeX forms."""

    if type(markdown) is not str or not markdown.strip():
        raise ValueError("recognized Markdown must be nonempty plain text")
    structural_arrows_removed = "\n".join(
        _remove_line_leading_diagram_connector(line)
        for line in markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    )
    return normalize_recognized_markdown_v3(structural_arrows_removed)


def _remove_line_leading_diagram_connector(line: str) -> str:
    match = _LINE_LEADING_DIAGRAM_CONNECTOR.match(line)
    if match is None:
        return line
    prefix = match.group("prefix")
    return f"{prefix if prefix.strip() else ''}{line[match.end():]}"
