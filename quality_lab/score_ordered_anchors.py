"""Score full-token anchor presence and first-occurrence source order."""

from __future__ import annotations

from dataclasses import dataclass

from quality_lab.rational_score import RationalScore
from quality_lab.tokenize_content_units import ContentToken, tokenize_content_units


@dataclass(frozen=True, slots=True)
class OrderedAnchor:
    """One source-indexed visible anchor and accepted token sequences."""

    id: str
    source_index: int
    accepted: tuple[str, ...]
    case_sensitive: bool = True

    def __post_init__(self) -> None:
        if type(self.id) is not str or not self.id:
            raise ValueError("anchor id must be a non-empty plain string")
        if type(self.source_index) is not int or self.source_index < 0:
            raise ValueError("anchor source_index must be a non-negative integer")
        if type(self.accepted) is not tuple or not self.accepted:
            raise ValueError("anchor accepted values must be a non-empty tuple")
        if type(self.case_sensitive) is not bool:
            raise TypeError("anchor case_sensitive must be an exact boolean")


@dataclass(frozen=True, slots=True)
class OrderedAnchorScore:
    """Anchor evidence including earliest offsets and duplicate occurrences."""

    presence: RationalScore
    first_token_offsets: tuple[int | None, ...]
    first_appearances_in_order: bool
    anchors_do_not_overlap: bool
    source_order_matches: bool
    image_count_matches: bool
    duplicate_occurrence_count: int

    @property
    def passes(self) -> bool:
        return (
            self.presence.numerator == self.presence.denominator
            and self.first_appearances_in_order
            and self.anchors_do_not_overlap
            and self.source_order_matches
            and self.image_count_matches
            and self.duplicate_occurrence_count == 0
        )


def score_ordered_anchors(
    anchors: tuple[OrderedAnchor, ...],
    recognized_text: str,
    *,
    actual_source_indices: tuple[int, ...],
    actual_image_count: int,
) -> OrderedAnchorScore:
    """Require every first full-token anchor to follow declared source order."""

    if type(anchors) is not tuple or not anchors:
        raise ValueError("ordered anchors must be a non-empty tuple")
    if type(actual_source_indices) is not tuple:
        raise TypeError("actual_source_indices must be a tuple")
    if any(type(index) is not int or index < 0 for index in actual_source_indices):
        raise ValueError("actual source indexes must be non-negative exact integers")
    if type(actual_image_count) is not int or actual_image_count < 0:
        raise ValueError("actual_image_count must be a non-negative integer")
    _validate_anchor_order(anchors)
    recognized_tokens = tokenize_content_units(recognized_text)
    occurrence_intervals: list[tuple[tuple[int, int], ...]] = []
    accepted_sequences: list[tuple[tuple[tuple[str, str], ...], ...]] = []
    for anchor in anchors:
        sequences = tuple(
            _token_key_sequence(value, case_sensitive=anchor.case_sensitive)
            for value in anchor.accepted
        )
        if len(set(sequences)) != len(sequences):
            raise ValueError(f"anchor {anchor.id!r} contains duplicate accepted forms")
        accepted_sequences.append(sequences)
        intervals = sorted(
            {
                interval
                for sequence in sequences
                for interval in _find_sequence_intervals(
                    recognized_tokens, sequence, case_sensitive=anchor.case_sensitive
                )
            }
        )
        starts = [start for start, _ in intervals]
        if len(starts) != len(set(starts)):
            raise ValueError(
                f"anchor {anchor.id!r} has ambiguous accepted forms at one offset"
            )
        occurrence_intervals.append(tuple(intervals))

    _reject_ambiguous_anchor_sequences(anchors, accepted_sequences)
    first_intervals = tuple(
        intervals[0] if intervals else None for intervals in occurrence_intervals
    )
    first_offsets = tuple(
        interval[0] if interval is not None else None for interval in first_intervals
    )
    present_offsets = [offset for offset in first_offsets if offset is not None]
    expected_source_indices = tuple(dict.fromkeys(anchor.source_index for anchor in anchors))
    expected_image_count = max(expected_source_indices) + 1
    return OrderedAnchorScore(
        presence=RationalScore(len(present_offsets), len(anchors)),
        first_token_offsets=first_offsets,
        first_appearances_in_order=(
            len(present_offsets) == len(anchors)
            and all(left < right for left, right in zip(present_offsets, present_offsets[1:]))
        ),
        anchors_do_not_overlap=_intervals_do_not_overlap(first_intervals),
        source_order_matches=actual_source_indices == expected_source_indices,
        image_count_matches=actual_image_count == expected_image_count,
        duplicate_occurrence_count=sum(
            max(0, len(intervals) - 1) for intervals in occurrence_intervals
        ),
    )


def _validate_anchor_order(anchors: tuple[OrderedAnchor, ...]) -> None:
    ids: set[str] = set()
    previous_source_index = -1
    for anchor in anchors:
        if not isinstance(anchor, OrderedAnchor):
            raise TypeError("anchors tuple contains a non-OrderedAnchor value")
        if anchor.id in ids:
            raise ValueError(f"duplicate anchor id: {anchor.id}")
        if anchor.source_index < previous_source_index:
            raise ValueError("anchor source indexes must be nondecreasing")
        ids.add(anchor.id)
        previous_source_index = anchor.source_index
    unique_source_indexes = tuple(dict.fromkeys(anchor.source_index for anchor in anchors))
    if unique_source_indexes != tuple(range(len(unique_source_indexes))):
        raise ValueError("anchor source indexes must be contiguous and start at zero")


def _token_key_sequence(value: str, *, case_sensitive: bool) -> tuple[tuple[str, str], ...]:
    tokens = tokenize_content_units(value)
    if not tokens:
        raise ValueError("anchor form must contain at least one scored token")
    return tuple(
        (token.kind, token.value if case_sensitive else token.value.casefold())
        for token in tokens
    )


def _find_sequence_intervals(
    recognized: tuple[ContentToken, ...],
    expected: tuple[tuple[str, str], ...],
    *,
    case_sensitive: bool,
) -> tuple[tuple[int, int], ...]:
    recognized_keys = tuple(
        (token.kind, token.value if case_sensitive else token.value.casefold())
        for token in recognized
    )
    width = len(expected)
    return tuple(
        (offset, offset + width)
        for offset in range(0, len(recognized_keys) - width + 1)
        if recognized_keys[offset : offset + width] == expected
    )


def _intervals_do_not_overlap(
    intervals: tuple[tuple[int, int] | None, ...]
) -> bool:
    present = tuple(interval for interval in intervals if interval is not None)
    return all(
        left_end <= right_start or right_end <= left_start
        for left_index, (left_start, left_end) in enumerate(present)
        for right_start, right_end in present[left_index + 1 :]
    )


def _reject_ambiguous_anchor_sequences(
    anchors: tuple[OrderedAnchor, ...],
    sequences: list[tuple[tuple[tuple[str, str], ...], ...]],
) -> None:
    for left_index, left in enumerate(anchors):
        for right_index in range(left_index + 1, len(anchors)):
            right = anchors[right_index]
            for left_sequence in sequences[left_index]:
                for right_sequence in sequences[right_index]:
                    if left.case_sensitive and right.case_sensitive:
                        overlaps = left_sequence == right_sequence
                    else:
                        overlaps = tuple((kind, value.casefold()) for kind, value in left_sequence) == tuple(
                            (kind, value.casefold()) for kind, value in right_sequence
                        )
                    if overlaps:
                        raise ValueError(
                            f"ambiguous accepted forms for anchors {left.id!r} and {right.id!r}"
                        )
