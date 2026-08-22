"""Validate one provider value as visible recognition Markdown."""

from __future__ import annotations

import unicodedata

from ..errors import ProviderError
from .looks_like_refusal import looks_like_refusal
from .remove_closed_html_comments import remove_closed_html_comments


def validate_provider_markdown(value: object) -> str:
    """Return visible Markdown or raise a redacted false-success error."""
    markdown: str = value if type(value) is str else ""
    try:
        markdown.encode("utf-8")
    except UnicodeEncodeError:
        raise ProviderError(
            "The configured provider returned recognition Markdown that is not "
            "valid UTF-8 text.",
            code="PROVIDER_RESPONSE_INVALID",
            details={"reason": "invalid_encoding"},
        ) from None
    inspected_markdown = remove_closed_html_comments(markdown)
    if not _contains_visible_content(inspected_markdown):
        raise ProviderError(
            "The configured provider returned no recognition Markdown.",
            code="PROVIDER_RESPONSE_INVALID",
            details={"reason": "empty"},
        )
    if looks_like_refusal(markdown):
        raise ProviderError(
            "The configured provider declined the request instead of recognizing it.",
            code="PROVIDER_REFUSED_RECOGNITION",
            details={"reason": "refusal"},
        )
    return markdown


def _contains_visible_content(value: str) -> bool:
    return any(unicodedata.category(character)[0] in {"L", "N", "S"} for character in value)
