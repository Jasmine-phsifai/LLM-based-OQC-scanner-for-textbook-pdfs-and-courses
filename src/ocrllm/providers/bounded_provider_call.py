"""Bound one injected-provider call with a caller-visible wall clock."""

from __future__ import annotations

import threading
from collections.abc import Callable


class ProviderDeadlineExceeded(Exception):
    """Internal signal that an injected provider outlived Config.timeout_seconds."""


class BoundedProviderCall:
    """Run one blocking call on a pre-warmed worker thread with a deadline.

    The worker is started and parked before the caller paces the request, so the
    request cadence measured at the provider is not disturbed by thread startup.
    """

    def __init__(self, call: Callable[[], object]) -> None:
        self._call = call
        self._parked = threading.Event()
        self._release = threading.Event()
        self._dispatch = False
        self._outcome: list[object] = []
        self._failure: list[BaseException] = []
        # Daemon: a provider that never returns cannot be killed, so the worker is
        # abandoned rather than allowed to block interpreter shutdown.
        self._thread = threading.Thread(
            target=self._run,
            name="ocrllm-provider-call",
            daemon=True,
        )

    def __enter__(self) -> BoundedProviderCall:
        self._thread.start()
        self._parked.wait()
        return self

    def __exit__(self, *exception_info: object) -> bool:
        # Unpark without dispatching: leaving the block without run_within means
        # the request was cancelled or paced out, and must never reach the provider.
        self._release.set()
        return False

    def run_within(self, timeout_seconds: float) -> object:
        """Release the parked call and return its result before the deadline."""
        self._dispatch = True
        self._release.set()
        self._thread.join(timeout_seconds)
        if self._thread.is_alive():
            raise ProviderDeadlineExceeded from None
        if self._failure:
            raise self._failure[0]
        return self._outcome[0]

    def _run(self) -> None:
        self._parked.set()
        self._release.wait()
        if not self._dispatch:
            return
        try:
            self._outcome.append(self._call())
        except BaseException as error:  # re-raised on the calling thread
            self._failure.append(error)
