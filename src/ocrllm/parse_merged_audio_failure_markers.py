"""Parse strict library-written merged-audio failure ranges."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .audio.build_long_audio_interval_windows import (
    INTERVAL_CONTEXT_SECONDS,
    LongAudioIntervalWindow,
)
from .errors import InvalidSource, ProviderError


_HEADING_TOKEN = "## OCRLLM audio slot "
_FAILURE_TOKEN = "OCRLLM_FAILED_AUDIO_SLOT"
_SECONDS = r"(?:0|[1-9][0-9]*)\.[0-9]{3}"
_HEADING = re.compile(
    r"^## OCRLLM audio slot (?P<index>[1-9][0-9]*) "
    rf"\((?P<start>{_SECONDS})-(?P<end>{_SECONDS})s\)$",
    re.MULTILINE,
)
_FAILURE_SECTION = re.compile(
    r"^## OCRLLM audio slot (?P<heading_index>[1-9][0-9]*) "
    rf"\((?P<start>{_SECONDS})-(?P<end>{_SECONDS})s\)\n\n"
    r"(?P<comment><!-- OCRLLM_FAILED_AUDIO_SLOT "
    r"index=(?P<marker_index>[1-9][0-9]*) "
    r"code=(?P<code>[A-Z][A-Z0-9_]*) -->)$",
    re.MULTILINE,
)


@dataclass(frozen=True, slots=True)
class MergedAudioFailureMarker:
    """Identify one exact failed slot, range, and replaceable comment."""

    slot_index: int
    window: LongAudioIntervalWindow
    comment: str
    code: str


def parse_merged_audio_failure_markers(
    markdown: str,
    *,
    duration_seconds: float,
) -> tuple[int, tuple[MergedAudioFailureMarker, ...]]:
    """Return the total slot count and exact failed interval markers."""
    if (
        type(markdown) is not str
        or not markdown.strip()
        or type(duration_seconds) not in (int, float)
        or not math.isfinite(float(duration_seconds))
        or duration_seconds <= 0
    ):
        _raise_invalid_markdown()
    headings = tuple(_HEADING.finditer(markdown))
    if not headings or markdown.count(_HEADING_TOKEN) != len(headings):
        _raise_invalid_markdown()

    rounded_duration = Decimal(f"{float(duration_seconds):.3f}")
    ranges: list[tuple[Decimal, Decimal]] = []
    for expected_index, heading in enumerate(headings, start=1):
        if int(heading.group("index")) != expected_index:
            _raise_invalid_markdown()
        start = _parse_seconds(heading.group("start"))
        end = _parse_seconds(heading.group("end"))
        expected_start = Decimal("0.000") if not ranges else ranges[-1][1]
        if start != expected_start or end <= start:
            _raise_invalid_markdown()
        ranges.append((start, end))
    if len(ranges) < 2 or ranges[-1][1] != rounded_duration:
        _raise_invalid_markdown()

    matches = tuple(_FAILURE_SECTION.finditer(markdown))
    if (
        not matches
        or markdown.count(_FAILURE_TOKEN) != len(matches)
        or len(matches) >= len(headings)
    ):
        _raise_invalid_markdown()

    markers: list[MergedAudioFailureMarker] = []
    for match in matches:
        heading_index = int(match.group("heading_index"))
        marker_index = int(match.group("marker_index"))
        slot_index = heading_index - 1
        code = match.group("code")
        if (
            heading_index != marker_index
            or not 0 <= slot_index < len(ranges)
            or code not in ProviderError.allowed_codes
            or markdown.count(match.group("comment")) != 1
        ):
            _raise_invalid_markdown()
        parsed_start = _parse_seconds(match.group("start"))
        parsed_end = _parse_seconds(match.group("end"))
        if (parsed_start, parsed_end) != ranges[slot_index]:
            _raise_invalid_markdown()
        logical_start = float(parsed_start)
        logical_end = (
            float(duration_seconds)
            if slot_index == len(ranges) - 1
            else float(parsed_end)
        )
        markers.append(
            MergedAudioFailureMarker(
                slot_index=slot_index,
                window=LongAudioIntervalWindow(
                    index=slot_index,
                    logical_start_seconds=logical_start,
                    logical_end_seconds=logical_end,
                    actual_start_seconds=max(
                        0.0,
                        logical_start - INTERVAL_CONTEXT_SECONDS,
                    ),
                    actual_end_seconds=min(
                        float(duration_seconds),
                        logical_end + INTERVAL_CONTEXT_SECONDS,
                    ),
                ),
                comment=match.group("comment"),
                code=code,
            )
        )

    indexes = tuple(marker.slot_index for marker in markers)
    if indexes != tuple(sorted(set(indexes))):
        _raise_invalid_markdown()
    return len(headings), tuple(markers)


def _parse_seconds(value: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation:
        _raise_invalid_markdown()


def _raise_invalid_markdown() -> None:
    raise InvalidSource(
        "The existing Markdown is not a repairable current OCRLLM audio result.",
        code="SOURCE_INVALID",
        details={"provider_calls_attempted": 0},
    ) from None
