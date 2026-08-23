"""Construct native Google SDK timeout options."""

from __future__ import annotations


def google_client_options(google_module: object, *, timeout_seconds: float):
    """Return the SDK's millisecond HttpOptions object."""
    timeout_ms = int(timeout_seconds * 1000)
    return google_module.types.HttpOptions(timeout=timeout_ms)
