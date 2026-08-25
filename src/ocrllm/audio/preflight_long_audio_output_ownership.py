"""Preflight new or resumed ownership of one long-audio output root."""

from __future__ import annotations

import os
from pathlib import Path

from ..errors import ConfigError, OutputError, OutputExists, ResumeStateError
from .long_audio_output_paths import (
    LONG_AUDIO_RESULT_NAME,
    LONG_AUDIO_RESUME_STATE_NAME,
    LongAudioOutputPaths,
)


def preflight_long_audio_output_ownership(
    paths: LongAudioOutputPaths,
    *,
    resume: bool,
) -> None:
    """Reject a new-run collision or an incomplete resume root without writes."""
    if type(resume) is not bool:
        raise ConfigError(
            "Long-audio resume mode must be a boolean.",
            code="CONFIG_INVALID",
        ) from None
    if not _is_canonical_path_plan(paths):
        raise OutputError(
            "The long-audio output path plan is invalid.",
            code="OUTPUT_PATH_INVALID",
        ) from None

    try:
        root_exists = os.path.lexists(paths.root)
        if not resume:
            if root_exists:
                raise OutputExists(
                    "The requested long-audio output directory already exists."
                ) from None
            return

        if not root_exists or not paths.root.is_dir():
            raise ResumeStateError(
                "The long-audio resume directory is missing or invalid.",
                code="RESUME_STATE_INVALID",
            ) from None
        if os.path.lexists(paths.result):
            raise OutputExists(
                "The requested long-audio result is already published."
            ) from None
        if not os.path.lexists(paths.resume_state) or not paths.resume_state.is_file():
            raise ResumeStateError(
                "The long-audio resume state is missing or invalid.",
                code="RESUME_STATE_INVALID",
            ) from None
    except (OutputExists, ResumeStateError):
        raise
    except (OSError, TypeError, ValueError) as error:
        raise OutputError(
            "The long-audio output ownership could not be inspected.",
            code="OUTPUT_PATH_INVALID",
        ) from error


def _is_canonical_path_plan(paths: object) -> bool:
    return (
        type(paths) is LongAudioOutputPaths
        and isinstance(paths.root, Path)
        and isinstance(paths.result, Path)
        and isinstance(paths.resume_state, Path)
        and paths.result == paths.root / LONG_AUDIO_RESULT_NAME
        and paths.resume_state == paths.root / LONG_AUDIO_RESUME_STATE_NAME
    )
