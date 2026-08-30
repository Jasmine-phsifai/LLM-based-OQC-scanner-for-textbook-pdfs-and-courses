"""Resolve one deterministic merged-audio Markdown target."""

from __future__ import annotations

from pathlib import Path

from ..errors import OutputError
from .normalize_output_stem import normalize_output_stem
from .resolve_resume_state_path import resolve_resume_state_path
from .validate_atomic_output_path import validate_atomic_output_path


def resolve_merged_audio_output_path(
    source: Path,
    *,
    output_path: str | Path | None,
) -> Path:
    """Use one explicit target or the fixed sibling source default."""
    if output_path is not None:
        if not isinstance(output_path, (str, Path)):
            raise OutputError(
                "output_path must be a string or Path.",
                code="OUTPUT_PATH_INVALID",
                details={"provider_calls_attempted": 0},
            ) from None
        resolved = Path(output_path)
    else:
        absolute_source = source.absolute()
        resolved = absolute_source.with_name(
            f"{normalize_output_stem(absolute_source.stem)}_ocrllm.md"
        )
    if resolved.suffix.casefold() != ".md":
        raise OutputError(
            "Merged-audio output_path must end in .md.",
            code="OUTPUT_PATH_INVALID",
            details={"provider_calls_attempted": 0},
        ) from None
    validate_atomic_output_path(resolved)
    validate_atomic_output_path(resolve_resume_state_path(resolved))
    return resolved
