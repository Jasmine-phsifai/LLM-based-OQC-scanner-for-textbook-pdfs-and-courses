"""Canonicalize the narrowly declared Phase 1 v3 presentations."""

from __future__ import annotations

import re

from quality_lab.normalize_recognized_markdown_v2 import (
    normalize_recognized_markdown_v2,
)


_LINE_LEADING_DIAGRAM_ARROW = re.compile(r"^ {0,3}→[ \t]+")
_RELATION_TYPOGRAPHY = str.maketrans({"⩾": "≥", "⩽": "≤"})


def normalize_recognized_markdown_v3(markdown: str) -> str:
    """Return v1-scorable Markdown for only the declared v2/v3 equivalents."""

    normalized_v2 = normalize_recognized_markdown_v2(markdown)
    return "\n".join(
        _LINE_LEADING_DIAGRAM_ARROW.sub("", line.translate(_RELATION_TYPOGRAPHY))
        for line in normalized_v2.split("\n")
    )
