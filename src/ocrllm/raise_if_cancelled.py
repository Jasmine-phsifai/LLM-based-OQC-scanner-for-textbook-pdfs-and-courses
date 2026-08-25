"""Honor an Event-compatible cancellation signal before recognition work."""

from __future__ import annotations

from .errors import Cancelled, ConfigError
from .validate_cancellation_signal import validate_cancellation_signal


def raise_if_cancelled(cancellation: object | None) -> None:
    """Raise ``Cancelled`` when an explicit Event-compatible signal is set."""
    is_set = validate_cancellation_signal(cancellation)
    if is_set is None:
        return

    try:
        cancelled = is_set()
    except Exception:
        raise ConfigError(
            "Config.cancellation could not be checked safely.",
            code="CONFIG_INVALID",
        ) from None
    if type(cancelled) is not bool:
        raise ConfigError(
            "Config.cancellation.is_set() must return a boolean.",
            code="CONFIG_INVALID",
        ) from None
    if cancelled:
        raise Cancelled("Recognition was cancelled before recognition work.") from None
