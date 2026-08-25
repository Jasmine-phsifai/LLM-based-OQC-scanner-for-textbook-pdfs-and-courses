"""Coerce one explicit video output directory."""

from __future__ import annotations

from pathlib import Path

from ..errors import OutputError


def coerce_video_output_directory(output_dir: object) -> Path:
    """Accept the public nonempty-string-or-Path contract."""
    if isinstance(output_dir, Path):
        return Path(output_dir)
    if type(output_dir) is str and output_dir.strip():
        return Path(output_dir)
    raise OutputError(
        "Video output_dir must be a nonempty string or Path.",
        code="OUTPUT_PATH_INVALID",
    ) from None
