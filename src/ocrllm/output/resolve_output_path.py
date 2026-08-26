"""Resolve one deterministic Markdown output path without filesystem access."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ..config import Config
from .normalize_output_stem import normalize_output_stem
from .resolve_image_resume_state_path import resolve_image_resume_state_path
from .validate_atomic_output_path import validate_atomic_output_path


def resolve_output_path(
    source_paths: Sequence[Path],
    *,
    profile: str,
    config: Config,
) -> Path | None:
    """Return the configured report path without filesystem access or changes."""
    output_dir = config.output_directory()
    if output_dir is None:
        return None
    first_stem = normalize_output_stem(source_paths[0].stem)
    filename_stem = (
        first_stem
        if len(source_paths) == 1
        else f"{first_stem}_plus_{len(source_paths) - 1}"
    )
    output_path = output_dir / f"{filename_stem}_{profile}.md"
    validate_atomic_output_path(output_path)
    validate_atomic_output_path(resolve_image_resume_state_path(output_path))
    return output_path
