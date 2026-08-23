"""Resolve one deterministic Markdown output path without filesystem access."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ..config import Config
from .normalize_output_stem import normalize_output_stem


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
    return output_dir / f"{filename_stem}_{profile}.md"
