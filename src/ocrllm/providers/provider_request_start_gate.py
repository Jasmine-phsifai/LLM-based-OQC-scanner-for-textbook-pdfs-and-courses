"""Coordinate high-resolution monotonic starts within one public operation."""

from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar, Token
from threading import Event, Lock
from typing import Iterator

from ..errors import Cancelled
from ..raise_if_cancelled import raise_if_cancelled


_CANCELLATION_POLL_SECONDS = 0.05
_CURRENT_GATE: ContextVar[ProviderRequestStartGate | None] = ContextVar(
    "ocrllm_provider_request_start_gate",
    default=None,
)


class ProviderRequestStartGate:
    """Serialize request starts without serializing provider response waits."""

    def __init__(self, interval_seconds: float) -> None:
        self._interval_seconds = interval_seconds
        self._lock = Lock()
        self._next_start_at = 0.0
        self._aborted = Event()

    def abort(self) -> None:
        """Prevent provider calls that have not passed this gate yet."""
        self._aborted.set()

    def wait(self, cancellation: object | None) -> None:
        """Wait until this operation's next provider request may start."""
        self._raise_if_aborted()
        raise_if_cancelled(cancellation)
        with self._lock:
            while True:
                self._raise_if_aborted()
                raise_if_cancelled(cancellation)
                now = time.perf_counter()
                remaining = self._next_start_at - now
                if remaining <= 0.0:
                    self._next_start_at = now + self._interval_seconds
                    return
                time.sleep(min(remaining, _CANCELLATION_POLL_SECONDS))

    def _raise_if_aborted(self) -> None:
        if self._aborted.is_set():
            raise Cancelled(
                "Recognition batch stopped before this provider request began."
            ) from None


@contextmanager
def activate_provider_request_start_gate(
    gate: ProviderRequestStartGate,
) -> Iterator[None]:
    """Expose one shared gate to provider calls in the current context."""
    token: Token[ProviderRequestStartGate | None] = _CURRENT_GATE.set(gate)
    try:
        yield
    finally:
        _CURRENT_GATE.reset(token)


@contextmanager
def reuse_or_create_provider_request_start_gate(
    interval_seconds: float,
) -> Iterator[None]:
    """Reuse a batch gate or create one for a direct recognition call."""
    current_gate = _CURRENT_GATE.get()
    if current_gate is not None:
        yield
        return

    gate = ProviderRequestStartGate(interval_seconds)
    with activate_provider_request_start_gate(gate):
        yield


def wait_for_provider_request_start(cancellation: object | None) -> None:
    """Apply the active operation's cadence immediately before dispatch."""
    gate = _CURRENT_GATE.get()
    if gate is not None:
        gate.wait(cancellation)
    else:
        raise_if_cancelled(cancellation)
