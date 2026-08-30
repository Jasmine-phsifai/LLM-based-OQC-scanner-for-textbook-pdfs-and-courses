"""Immutable identity for one planned audio time range."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AudioSlice:
    """Describe one logical range and its context-padded source range."""

    source: Path
    index: int
    logical_start_seconds: float
    logical_end_seconds: float
    actual_start_seconds: float
    actual_end_seconds: float
