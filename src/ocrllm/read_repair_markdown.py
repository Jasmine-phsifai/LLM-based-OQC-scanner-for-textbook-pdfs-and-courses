"""Read one existing repair target only after ordinary state is absent."""

from __future__ import annotations

import os
from pathlib import Path

from .errors import InvalidSource, OutputError, ResumeStateError


def read_repair_markdown(output_path: Path, *, state_path: Path) -> str:
    """Return strict UTF-8 Markdown or direct the caller back to resume."""
    if os.path.lexists(state_path):
        raise ResumeStateError(
            "The ordinary resume state still exists; use resume instead.",
            code="RESUME_STATE_INVALID",
            details={"provider_calls_attempted": 0},
        ) from None
    if not os.path.lexists(output_path):
        raise InvalidSource(
            "The partial Markdown does not exist.",
            code="SOURCE_NOT_FOUND",
            details={"provider_calls_attempted": 0},
        ) from None
    if not output_path.is_file():
        raise OutputError(
            "The partial Markdown target is not a regular file.",
            code="OUTPUT_PATH_INVALID",
            details={"provider_calls_attempted": 0},
        ) from None
    try:
        return output_path.read_text(encoding="utf-8")
    except UnicodeError as error:
        raise InvalidSource(
            "The partial Markdown is not valid UTF-8.",
            code="SOURCE_INVALID",
            details={"provider_calls_attempted": 0},
        ) from error
    except (OSError, ValueError) as error:
        raise InvalidSource(
            "The partial Markdown could not be read.",
            code="SOURCE_UNREADABLE",
            details={"provider_calls_attempted": 0},
        ) from error
