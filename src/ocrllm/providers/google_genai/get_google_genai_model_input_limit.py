"""Read one selected model's advertised input-token limit."""

from __future__ import annotations

from ...errors import ProviderError


def get_google_genai_model_input_limit(
    rows: tuple[object, ...],
    *,
    model: str,
) -> int | None:
    """Return a positive selected-model limit, or None when not advertised."""
    for row in rows:
        try:
            name = getattr(row, "name", None)
            actions = getattr(row, "supported_actions", ())
            supports_generate = actions is not None and "generateContent" in actions
        except Exception:
            continue
        if (
            type(name) is not str
            or name.removeprefix("models/") != model
            or not supports_generate
        ):
            continue
        try:
            limit = getattr(row, "input_token_limit", None)
        except Exception:
            _raise_invalid_limit(model)
        if limit is None:
            return None
        if type(limit) is not int or limit <= 0:
            _raise_invalid_limit(model)
        return limit
    return None


def _raise_invalid_limit(model: str) -> None:
    raise ProviderError(
        "Google GenAI returned invalid selected-model input metadata.",
        code="PROVIDER_RESPONSE_INVALID",
        details={
            "provider": "google",
            "model": model,
            "failure_scope": "response",
        },
    ) from None
