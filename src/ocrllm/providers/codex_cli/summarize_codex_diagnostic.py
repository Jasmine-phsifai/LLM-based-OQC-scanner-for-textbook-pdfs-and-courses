"""Retain bounded failure signals without publishing CLI text or credentials."""
import hashlib
import re


def summarize_codex_diagnostic(source, text):
    """Signals describe observed wording, not a retry policy or proven cause."""
    if not isinstance(text, str) or not text.strip():
        return None
    sample = text[-8192:]
    lower = sample.casefold()
    markers = {
        "usage_limit": ("usage limit", "insufficient_quota", "quota exceeded"),
        "rate_limit": ("rate limit", "rate_limit_exceeded", "too many requests"),
        "authentication": ("unauthorized", "authentication", "invalid_api_key", "token expired"),
        "connection": ("connection", "stream disconnected", "error sending request", "dns", "tls"),
        "timeout": ("timed out", "timeout"),
    }
    return {
        "source": source,
        "signals": [name for name, words in markers.items() if any(word in lower for word in words)],
        "http_status_codes": sorted({int(code) for code in re.findall(
            r"(?:http(?:/\d(?:\.\d)?)?|status(?:\s+code)?)\s*[:=]?\s*([45]\d\d)\b", lower)}),
        "sample_sha256": hashlib.sha256(sample.encode("utf-8", errors="replace")).hexdigest(),
        "sample_characters": len(sample),
        "truncated": len(text) > len(sample),
    }
