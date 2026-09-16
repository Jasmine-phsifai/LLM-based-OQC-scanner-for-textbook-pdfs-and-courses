"""Copy request images to safe ASCII staging names for Codex CLI."""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path

from ...errors import InvalidSource


def stage_codex_images(
    image_paths: Sequence[Path],
    staging_dir: Path,
) -> list[Path]:
    """Stage images as image_NNN files and prove each copy is nonempty."""
    staged_paths: list[Path] = []
    for index, path in enumerate(image_paths, start=1):
        source = Path(path)
        suffix = source.suffix.lower() if source.suffix.isascii() else ""
        destination = staging_dir / f"image_{index:03d}{suffix}"
        try:
            shutil.copyfile(source, destination)
            if destination.stat().st_size <= 0:
                raise OSError("staged image is empty")
        except FileNotFoundError:
            raise InvalidSource(
                "An image staged for Codex CLI recognition is missing.",
                code="SOURCE_NOT_FOUND",
                details={"path": str(source)},
            ) from None
        except OSError:
            raise InvalidSource(
                "An image staged for Codex CLI recognition is unreadable.",
                code="SOURCE_UNREADABLE",
                details={"path": str(source)},
            ) from None
        staged_paths.append(destination)
    return staged_paths
