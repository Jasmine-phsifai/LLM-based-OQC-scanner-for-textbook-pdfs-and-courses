"""Validate the structural contract of one cancellation signal."""

from __future__ import annotations

from collections.abc import Callable

from .errors import ConfigError


def validate_cancellation_signal(
    cancellation: object | None,
) -> Callable[[], object] | None:
    """Return a callable ``is_set`` without observing cancellation state."""
    if cancellation is None:
        return None

    try:
        is_set = getattr(cancellation, "is_set", None)
    except Exception:
        raise ConfigError(
            "Config.cancellation could not be inspected safely.",
            code="CONFIG_INVALID",
        ) from None
    if not callable(is_set):
        raise ConfigError(
            "Config.cancellation must expose a callable is_set() method.",
            code="CONFIG_INVALID",
        ) from None
    return is_set
