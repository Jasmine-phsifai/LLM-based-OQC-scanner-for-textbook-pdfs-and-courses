"""Validate and prepare the owned PDF sidecar directory."""

from __future__ import annotations

import os
from pathlib import Path

from ..config import Config
from ..errors import OutputError, OutputExists, ResumeStateError


def prepare_pdf_state_directory(output_path: Path, *, config: Config) -> Path:
    """Return the same-named directory used by PDF image-group checkpoints."""
    state_directory = output_path.with_suffix("")
    try:
        state_exists = os.path.lexists(state_directory)
        if state_exists and not state_directory.is_dir():
            raise OutputError(
                "The PDF state path is not a directory.",
                code="OUTPUT_PATH_INVALID",
            ) from None
        if state_exists and not config.resume and not config.overwrite:
            raise OutputExists("The requested PDF state directory already exists.") from None
        if config.resume and output_path.exists() and not state_exists:
            raise ResumeStateError(
                "Existing PDF output has no resumable image-group directory.",
                code="RESUME_STATE_INVALID",
            ) from None
        state_directory.mkdir(parents=True, exist_ok=True)
    except (OutputError, OutputExists, ResumeStateError):
        raise
    except (OSError, ValueError) as error:
        raise OutputError(
            "The PDF state directory could not be created or opened.",
            code="OUTPUT_PATH_INVALID",
        ) from error
    return state_directory
