"""Validate one provider value as visible recognition Markdown."""

from __future__ import annotations

import unicodedata

from ..errors import ProviderError
from .looks_like_refusal import looks_like_refusal


def validate_provider_markdown(value: object) -> str:
    """Return visible Markdown or raise a redacted false-success error."""
    if type(value) is not str or not _contains_visible_content(value):
        raise ProviderError(
            "The configured provider returned no recognition Markdown.",
            code="PROVIDER_RESPONSE_INVALID",
            details={"reason": "empty"},
        )
    if looks_like_refusal(value):
        raise ProviderError(
            "The configured provider declined the request instead of recognizing it.",
            code="PROVIDER_REFUSED_RECOGNITION",
            details={"reason": "refusal"},
        )
    return value


def _contains_visible_content(value: str) -> bool:
    return any(unicodedata.category(character)[0] in {"L", "N", "S"} for character in value)
