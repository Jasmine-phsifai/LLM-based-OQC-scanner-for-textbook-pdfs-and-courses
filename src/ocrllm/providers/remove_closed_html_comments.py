"""Remove closed HTML comments from a Markdown inspection view."""

from __future__ import annotations

import re


_CLOSED_HTML_COMMENT = re.compile(r"<!--.*?-->", flags=re.DOTALL)


def remove_closed_html_comments(markdown: str) -> str:
    """Return Markdown without closed comments, leaving malformed input intact."""
    return _CLOSED_HTML_COMMENT.sub("", markdown)
