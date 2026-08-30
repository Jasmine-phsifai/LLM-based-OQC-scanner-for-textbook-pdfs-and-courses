"""Validate one resumable Markdown output and its sidecar ownership."""

from __future__ import annotations

import os
from pathlib import Path

from ..errors import OutputError, OutputExists, ResumeStateError


def preflight_resumable_markdown_output(
    output_path: Path,
    state_path: Path,
    *,
    resume: bool,
    overwrite: bool,
) -> None:
    """Prepare the parent and reject conflicting output/state objects."""
    if type(resume) is not bool or type(overwrite) is not bool or (resume and overwrite):
        raise OutputError(
            "Resume and overwrite options are invalid.",
            code="OUTPUT_PATH_INVALID",
        ) from None
    parent = output_path.parent
    try:
        if parent.exists() and not parent.is_dir():
            raise OutputError(
                "The Markdown output parent is not a directory.",
                code="OUTPUT_PATH_INVALID",
            ) from None
        parent.mkdir(parents=True, exist_ok=True)
    except OutputError:
        raise
    except (OSError, ValueError):
        raise OutputError(
            "The Markdown output parent could not be prepared.",
            code="OUTPUT_PATH_INVALID",
        ) from None

    output_exists = os.path.lexists(output_path)
    state_exists = os.path.lexists(state_path)
    if output_exists and not output_path.is_file():
        raise OutputError(
            "The Markdown target is not a regular file.",
            code="OUTPUT_PATH_INVALID",
        ) from None
    if state_exists and not state_path.is_file():
        error_type = ResumeStateError if resume else OutputError
        error_code = "RESUME_STATE_INVALID" if resume else "OUTPUT_PATH_INVALID"
        raise error_type(
            "The resume-state target is not a regular file.",
            code=error_code,
        ) from None
    if resume:
        if not state_exists:
            raise ResumeStateError(
                "The recognition resume state does not exist.",
                code="RESUME_STATE_INVALID",
            ) from None
        return
    if not overwrite and (output_exists or state_exists):
        raise OutputExists(
            "The Markdown output or resume state already exists."
        ) from None
