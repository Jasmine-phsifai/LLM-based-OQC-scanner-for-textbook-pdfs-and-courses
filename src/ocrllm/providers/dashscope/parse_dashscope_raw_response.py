"""Reject DashScope partial-response headers before parsing response JSON."""

from __future__ import annotations

from ...errors import ProviderError


def parse_dashscope_raw_response(raw_response: object, *, model: str) -> object:
    """Return the parsed SDK response only when headers report completeness."""
    details = {"provider": "dashscope", "model": model}
    try:
        headers = getattr(raw_response, "headers")
        get_header = getattr(headers, "get")
        parse = getattr(raw_response, "parse")
        if not callable(get_header) or not callable(parse):
            raise TypeError
        partial_header = get_header("x-dashscope-partialresponse")
    except Exception:
        raise ProviderError(
            "DashScope returned an unreadable raw response boundary.",
            code="PROVIDER_RESPONSE_INVALID",
            details={**details, "reason": "raw_boundary"},
        ) from None

    if partial_header is not None:
        if type(partial_header) is not str:
            raise ProviderError(
                "DashScope returned an invalid partial-response header.",
                code="PROVIDER_RESPONSE_INVALID",
                details={**details, "reason": "partial_header"},
            ) from None
        normalized_header = partial_header.strip().casefold()
        if normalized_header == "true":
            raise ProviderError(
                "DashScope returned content truncated by a provider timeout.",
                code="PROVIDER_RESPONSE_INVALID",
                details={**details, "reason": "partial_timeout"},
            ) from None
        if normalized_header != "false":
            raise ProviderError(
                "DashScope returned an invalid partial-response header.",
                code="PROVIDER_RESPONSE_INVALID",
                details={**details, "reason": "partial_header"},
            ) from None

    try:
        return parse()
    except Exception:
        raise ProviderError(
            "DashScope returned a response that could not be parsed safely.",
            code="PROVIDER_RESPONSE_INVALID",
            details={**details, "reason": "raw_parse"},
        ) from None
