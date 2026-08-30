"""Resolve one deterministic merged-image Markdown target."""

from __future__ import annotations

from pathlib import Path

from ..errors import OutputError
from .normalize_output_stem import normalize_output_stem
from .resolve_image_resume_state_path import resolve_image_resume_state_path
from .validate_atomic_output_path import validate_atomic_output_path


def resolve_merged_image_output_path(
    batches: tuple[tuple[Path, ...], ...],
    *,
    output_path: str | Path | None,
) -> Path:
    """Apply the fixed sibling-or-single-folder default without filesystem writes."""
    leaves = tuple(path for batch in batches for path in batch)
    if output_path is not None:
        if not isinstance(output_path, (str, Path)):
            raise OutputError(
                "output_path must be a string or Path.",
                code="OUTPUT_PATH_INVALID",
            ) from None
        resolved = Path(output_path)
    elif len(leaves) == 1:
        source = leaves[0].absolute()
        resolved = source.with_name(f"{normalize_output_stem(source.stem)}_ocrllm.md")
    else:
        absolute_parents = tuple(path.absolute().parent for path in leaves)
        first_parent = absolute_parents[0]
        if any(parent != first_parent for parent in absolute_parents[1:]):
            raise OutputError(
                "Mixed-parent image batches require an explicit output_path.",
                code="OUTPUT_PATH_INVALID",
                details={"provider_calls_attempted": 0},
            ) from None
        resolved = first_parent.parent / (
            f"{normalize_output_stem(first_parent.name)}_ocrllm.md"
        )
    if resolved.suffix.casefold() != ".md":
        raise OutputError(
            "Merged-image output_path must end in .md.",
            code="OUTPUT_PATH_INVALID",
        ) from None
    validate_atomic_output_path(resolved)
    validate_atomic_output_path(resolve_image_resume_state_path(resolved))
    return resolved
