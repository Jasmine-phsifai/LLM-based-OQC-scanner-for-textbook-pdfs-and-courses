"""Plan one deterministic long-audio output layout without side effects."""

from __future__ import annotations

from pathlib import Path

from ..errors import OutputError
from ..output.normalize_output_stem import normalize_output_stem
from ..output.validate_atomic_output_path import validate_atomic_output_path
from .long_audio_output_paths import (
    LONG_AUDIO_RESULT_NAME,
    LONG_AUDIO_RESUME_STATE_NAME,
    LongAudioOutputPaths,
)


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
    validate_atomic_output_path(paths.result)
    validate_atomic_output_path(paths.resume_state)

    try:
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
