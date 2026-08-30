"""Normalize the exact already-batched merged-image input."""

from __future__ import annotations

from pathlib import Path

from .errors import InvalidSource


def normalize_merged_image_batches(
    batches: tuple[tuple[str | Path, ...], ...],
) -> tuple[tuple[Path, ...], ...]:
    """Require nonempty exact tuples and concrete image leaves."""
    if type(batches) is not tuple or not batches:
        raise InvalidSource(
            "Merged-image recognition requires a nonempty exact tuple of batches.",
            code="SOURCE_INVALID",
            details={"provider_calls_attempted": 0},
        ) from None
    normalized: list[tuple[Path, ...]] = []
    for batch in batches:
        if type(batch) is not tuple or not batch:
            raise InvalidSource(
                "Each merged-image batch must be a nonempty exact tuple.",
                code="SOURCE_INVALID",
                details={"provider_calls_attempted": 0},
            ) from None
        if any(not isinstance(source, (str, Path)) for source in batch):
            raise InvalidSource(
                "Merged-image batches may contain only strings or Paths.",
                code="SOURCE_INVALID",
                details={"provider_calls_attempted": 0},
            ) from None
        normalized.append(tuple(Path(source) for source in batch))
    return tuple(normalized)
