"""Validate and prepare the owned PDF sidecar directory."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from ..config import Config
from ..errors import OutputError, OutputExists, ResumeStateError


def prepare_pdf_state_directory(output_path: Path, *, config: Config) -> Path:
    """Return the same-named directory used by PDF image-group checkpoints."""
    state_directory = output_path.with_suffix("")
    try:
        state_exists = os.path.lexists(state_directory)
        if state_exists:
            state_info = os.lstat(state_directory)
            reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            is_reparse_point = bool(
                getattr(state_info, "st_file_attributes", 0) & reparse_flag
            )
            if not stat.S_ISDIR(state_info.st_mode) or is_reparse_point:
                raise OutputError(
                    "The PDF state path is not an owned directory.",
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
