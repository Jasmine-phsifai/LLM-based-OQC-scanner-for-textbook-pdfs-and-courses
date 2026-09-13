"""Latch caller drain requests without cancelling an admitted provider call."""

from threading import Event

from .errors import Cancelled
from .raise_if_cancelled import raise_if_cancelled
from .validate_cancellation_signal import validate_cancellation_signal


class ProviderDispatchStopped(Exception):
    """Internal gate result; the owner acknowledges only after draining lanes."""


class CooperativeStop:
    """Shared by existing lanes; internal abort and caller drain stay distinct."""

    def __init__(self, signal: object | None) -> None:
        validate_cancellation_signal(signal)
        self._signal = signal
        self._requested = Event()
        self._abort = Event()

    @property
    def enabled(self) -> bool:
        return self._signal is not None

    def set(self) -> None:
        self._abort.set()

    def is_set(self) -> bool:
        if not self._requested.is_set():
            try:
                raise_if_cancelled(self._signal)
            except Cancelled:
                self._requested.set()
        return self._requested.is_set() or self._abort.is_set()

    def acknowledge(self, *, current_call_count: int) -> None:
        """Only the owner calls this after every admitted call has checkpointed."""
        self.is_set()
        if self._requested.is_set():
            raise Cancelled(
                "Recognition stopped safely after saving completed provider calls.",
                details={"safe_stop": True, "resume_available": True,
                         "current_call_count": current_call_count,
                         "provider_calls_attempted": current_call_count},
            ) from None
