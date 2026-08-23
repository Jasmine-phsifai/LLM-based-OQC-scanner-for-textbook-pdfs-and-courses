"""Close one native Google client without hiding primary failures."""

from __future__ import annotations

from ...errors import ProviderError


def close_google_genai_client(client: object | None) -> ProviderError | None:
    """Return a cleanup error, or None after a successful/no-op close."""
    if client is None:
        return None
    try:
        close = getattr(client, "close", None)
        if not callable(close):
            raise TypeError
        close()
    except Exception:
        return ProviderError(
            "The Google GenAI client could not be closed safely.",
            code="PROVIDER_RESPONSE_INVALID",
            details={"provider": "google"},
        )
    return None
