"""Aggregate exact cleanup outcomes across long-audio slots."""

from __future__ import annotations


def aggregate_long_audio_cleanup(
    values: tuple[bool | None, ...],
) -> bool | None:
    """Return false on any failure, true when all are true, else unknown."""
    if any(value is False for value in values):
        return False
    if values and all(value is True for value in values):
        return True
    return None
