"""Load the optional native Google GenAI SDK lazily."""

from __future__ import annotations

from ...errors import DependencyMissing


def load_google_genai():
    """Return ``google.genai`` or one stable optional-dependency failure."""
    try:
        from google import genai
    except (ImportError, ModuleNotFoundError):
        raise DependencyMissing(
            "Google GenAI support requires the 'google' optional extra.",
            details={"extra": "google"},
        ) from None
    try:
        client = genai.Client
        http_options = genai.types.HttpOptions
        from_bytes = genai.types.Part.from_bytes
    except Exception:
        raise DependencyMissing(
            "The installed google-genai package does not expose the required API.",
            details={"extra": "google"},
        ) from None
    if not all(callable(value) for value in (client, http_options, from_bytes)):
        raise DependencyMissing(
            "The installed google-genai package does not expose the required API.",
            details={"extra": "google"},
        ) from None
    return genai
