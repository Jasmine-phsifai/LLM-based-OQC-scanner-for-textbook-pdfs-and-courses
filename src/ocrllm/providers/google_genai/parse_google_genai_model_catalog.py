"""Parse native Google generateContent model catalog rows."""

from __future__ import annotations

from ...errors import ProviderError


def parse_google_genai_model_catalog(rows: object) -> tuple[str, ...]:
    """Return ordered canonical IDs for models serving generateContent."""
    identifiers: list[str] = []
    try:
        iterator = iter(rows)
    except Exception:
        raise ProviderError(
            "Google GenAI returned an invalid model catalog.",
            code="PROVIDER_RESPONSE_INVALID",
            details={"provider": "google"},
        ) from None
    for row in iterator:
        try:
            name = getattr(row, "name", None)
            actions = getattr(row, "supported_actions", ())
            supports_generate = actions is not None and "generateContent" in actions
        except Exception:
            continue
        if type(name) is not str or not supports_generate:
            continue
        canonical = name.removeprefix("models/")
        if canonical and canonical == canonical.strip() and canonical not in identifiers:
            identifiers.append(canonical)
    return tuple(identifiers)
