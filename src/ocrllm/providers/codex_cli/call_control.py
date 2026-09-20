"""Carry merged admission/drain control only into the Codex CLI adapter."""
from contextlib import contextmanager
from contextvars import ContextVar
import time

_CONTROL = ContextVar("ocrllm_codex_call_control", default=None)


@contextmanager
def codex_call_control(*, stop_requested=None, timeout_seconds=None, before_dispatch=None):
    token = _CONTROL.set({
        "stop_requested": stop_requested,
        "before_dispatch": before_dispatch,
        "deadline": time.monotonic() + timeout_seconds if timeout_seconds is not None else None,
    })
    try:
        yield
    finally:
        _CONTROL.reset(token)


def stop_requested():
    control = _CONTROL.get()
    signal = control["stop_requested"] if control else None
    return signal is not None and signal.is_set()


def remaining_seconds(default):
    control = _CONTROL.get()
    deadline = control["deadline"] if control else None
    return min(default, deadline - time.monotonic()) if deadline is not None else default


def before_dispatch():
    """Invoke the owner reservation after admission, immediately before spawn."""
    control = _CONTROL.get()
    callback = control.get("before_dispatch") if control else None
    if callback is not None:
        callback()
