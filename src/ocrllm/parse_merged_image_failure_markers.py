"""Parse only strict library-written merged-image failure sections."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .errors import InvalidSource, ProviderError


_FAILURE_TOKEN = "OCRLLM_FAILED_IMAGE_SLOT"
_SOURCE_LABEL = r"[1-9][0-9]*(?:-[1-9][0-9]*)?"
_FAILURE_SECTION = re.compile(
    r"^## OCRLLM image slot (?P<heading_index>[1-9][0-9]*) "
    rf"\((?P<heading_sources>{_SOURCE_LABEL})\)\n\n"
    r"(?P<comment><!-- OCRLLM_FAILED_IMAGE_SLOT "
    r"index=(?P<marker_index>[1-9][0-9]*) "
    rf"sources=(?P<marker_sources>{_SOURCE_LABEL}) "
    r"code=(?P<code>[A-Z][A-Z0-9_]*) -->)$",
    re.MULTILINE,
)


@dataclass(frozen=True, slots=True)
class MergedImageFailureMarker:
    """Identify one exact failed absolute slot and its replaceable comment."""

    slot_index: int
    comment: str


def parse_merged_image_failure_markers(
    markdown: str,
    batches: tuple[tuple[Path, ...], ...],
) -> tuple[MergedImageFailureMarker, ...]:
    """Return ordered strict markers that exactly match caller batch membership."""
    if type(markdown) is not str or not markdown.strip():
        _raise_invalid_markdown()
    expected_labels = _expected_source_labels(batches)
    matches = tuple(_FAILURE_SECTION.finditer(markdown))
    if (
        not matches
        or markdown.count(_FAILURE_TOKEN) != len(matches)
        or len(matches) >= len(batches)
    ):
        _raise_invalid_markdown()

    markers: list[MergedImageFailureMarker] = []
    for match in matches:
        heading_index = int(match.group("heading_index"))
        marker_index = int(match.group("marker_index"))
        heading_sources = match.group("heading_sources")
        marker_sources = match.group("marker_sources")
        code = match.group("code")
        slot_index = heading_index - 1
        if (
            heading_index != marker_index
            or not 0 <= slot_index < len(batches)
            or heading_sources != marker_sources
            or marker_sources != expected_labels[slot_index]
            or code not in ProviderError.allowed_codes
            or markdown.count(match.group("comment")) != 1
        ):
            _raise_invalid_markdown()
        markers.append(
            MergedImageFailureMarker(
                slot_index=slot_index,
                comment=match.group("comment"),
            )
        )

    indexes = tuple(marker.slot_index for marker in markers)
    if indexes != tuple(sorted(set(indexes))):
        _raise_invalid_markdown()
    return tuple(markers)


def _expected_source_labels(
    batches: tuple[tuple[Path, ...], ...],
) -> tuple[str, ...]:
    labels: list[str] = []
    first = 1
    for batch in batches:
        last = first + len(batch) - 1
        labels.append(str(first) if first == last else f"{first}-{last}")
        first = last + 1
    return tuple(labels)


def _raise_invalid_markdown() -> None:
    raise InvalidSource(
        "The existing Markdown is not a repairable current OCRLLM image result.",
        code="SOURCE_INVALID",
        details={"provider_calls_attempted": 0},
    ) from None
