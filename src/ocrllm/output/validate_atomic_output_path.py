"""Reject an atomic sibling path unsupported by legacy Windows limits."""

from __future__ import annotations

import os
from pathlib import Path

from ..errors import OutputError


_MAX_LEGACY_WINDOWS_PATH_UNITS = 259
_ATOMIC_TEMPORARY_PATH_PROBE_NAME = f".ocrllm-{'0' * 32}.tmp"


def validate_atomic_output_path(output_path: Path) -> None:
    """Validate one fixed output and its UUID-shaped atomic sibling."""
    if os.name != "nt":
        return
    try:
        temporary_path = output_path.with_name(_ATOMIC_TEMPORARY_PATH_PROBE_NAME)
        path_units = tuple(
            len(os.path.abspath(os.fspath(path)).encode("utf-16-le")) // 2
            for path in (output_path, temporary_path)
        )
    except (OSError, ValueError) as error:
        raise OutputError(
            "The atomic output path could not be inspected.",
            code="OUTPUT_PATH_INVALID",
            details={"provider_calls_attempted": 0},
        ) from error
    if any(units > _MAX_LEGACY_WINDOWS_PATH_UNITS for units in path_units):
        raise OutputError(
            "The atomic output path exceeds the supported Windows limit.",
            code="OUTPUT_PATH_INVALID",
            details={"provider_calls_attempted": 0},
        ) from None
