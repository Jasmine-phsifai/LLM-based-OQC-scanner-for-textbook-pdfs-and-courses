"""Plan one deterministic long-audio output layout without side effects."""

from __future__ import annotations

import os
from pathlib import Path

from ..errors import OutputError
from ..output.normalize_output_stem import normalize_output_stem
from .long_audio_output_paths import (
    LONG_AUDIO_RESULT_NAME,
    LONG_AUDIO_RESUME_STATE_NAME,
    LongAudioOutputPaths,
)


_MAX_LEGACY_WINDOWS_PATH_UNITS = 259
_ATOMIC_TEMPORARY_PATH_PROBE_NAME = f".ocrllm-{'0' * 32}.tmp"


def plan_long_audio_output_paths(
    source_path: Path,
    output_dir: Path,
) -> LongAudioOutputPaths:
    """Return fixed audio-owned paths after side-effect-free structural checks."""
    if not isinstance(source_path, Path) or not isinstance(output_dir, Path):
        raise OutputError(
            "Long-audio source and output directory must be Path values.",
            code="OUTPUT_PATH_INVALID",
        ) from None

    root = output_dir / normalize_output_stem(source_path.stem)
    paths = LongAudioOutputPaths(
        root=root,
        result=root / LONG_AUDIO_RESULT_NAME,
        resume_state=root / LONG_AUDIO_RESUME_STATE_NAME,
    )
    # Both long-audio state and Markdown writers use this UUID-shaped sibling.
    atomic_temporary_path = paths.root / _ATOMIC_TEMPORARY_PATH_PROBE_NAME

    try:
        if os.name == "nt" and any(
            _windows_path_units(path) > _MAX_LEGACY_WINDOWS_PATH_UNITS
            for path in (
                paths.root,
                paths.result,
                paths.resume_state,
                atomic_temporary_path,
            )
        ):
            raise OutputError(
                "The long-audio output path exceeds the supported Windows limit.",
                code="OUTPUT_PATH_INVALID",
            ) from None
        if output_dir.exists() and not output_dir.is_dir():
            raise OutputError(
                "The long-audio output parent must be a directory.",
                code="OUTPUT_PATH_INVALID",
            ) from None
    except OutputError:
        raise
    except (OSError, ValueError) as error:
        raise OutputError(
            "The long-audio output path could not be inspected.",
            code="OUTPUT_PATH_INVALID",
        ) from error

    return paths


def _windows_path_units(path: Path) -> int:
    absolute = os.path.abspath(os.fspath(path))
    return len(absolute.encode("utf-16-le")) // 2
