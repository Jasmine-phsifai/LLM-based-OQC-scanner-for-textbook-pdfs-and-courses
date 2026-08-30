"""Score predeclared critical values as non-overlapping token sequences."""

from __future__ import annotations

from dataclasses import dataclass

from quality_lab.rational_score import RationalScore
from quality_lab.tokenize_content_units import ContentToken, tokenize_content_units


@dataclass(frozen=True, slots=True)
class ExpectedCriticalSlot:
    """One counted critical value and its accepted full-token spellings."""

    id: str
    accepted: tuple[str, ...]
    count: int = 1
    case_sensitive: bool = True

    def __post_init__(self) -> None:
        if type(self.id) is not str or not self.id or self.id != self.id.strip():
            raise ValueError("critical slot id must be a non-empty trimmed string")
        if type(self.accepted) is not tuple or not self.accepted:
            raise ValueError("critical slot accepted forms must be a non-empty tuple")
        if any(type(value) is not str or not value.strip() for value in self.accepted):
            raise ValueError("critical slot accepted forms must be non-empty plain strings")
        if type(self.count) is not int or self.count <= 0:
            raise ValueError("critical slot count must be a positive exact integer")
        if type(self.case_sensitive) is not bool:
            raise TypeError("critical slot case_sensitive must be an exact boolean")


@dataclass(frozen=True, slots=True)
class CriticalSlotScore:
    """Exact critical-slot accuracy, omissions, and duplicate evidence."""

    accuracy: RationalScore
    missing_slot_ids: tuple[str, ...]
    duplicate_occurrence_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.accuracy, RationalScore):
            raise TypeError("critical slot accuracy must be a RationalScore")
        if type(self.missing_slot_ids) is not tuple or any(
            type(value) is not str or not value for value in self.missing_slot_ids
        ):
            raise TypeError("missing critical slot ids must be a tuple of non-empty strings")
        if len(self.missing_slot_ids) != (
            self.accuracy.denominator - self.accuracy.numerator
        ):
            raise ValueError("missing critical slot ids must match the accuracy counts")
        if (
            type(self.duplicate_occurrence_count) is not int
            or self.duplicate_occurrence_count < 0
        ):
            raise ValueError("duplicate critical slot count must be a non-negative integer")

    @property
    def passes(self) -> bool:
        """Return whether every slot occurs exactly the declared number of times."""

        return (
            self.accuracy.numerator == self.accuracy.denominator
            and self.duplicate_occurrence_count == 0
        )


@dataclass(frozen=True, slots=True)
class _CandidateInterval:
    slot_index: int
    start: int
    end: int


def score_critical_slots(
    expected: tuple[ExpectedCriticalSlot, ...],
    recognized_text: str,
) -> CriticalSlotScore:
    """Match the maximum number of declared slots without reusing any token."""

    canonical_slots = _validate_and_sort_slots(expected)
    recognized_tokens = tokenize_content_units(recognized_text)
    candidates: list[_CandidateInterval] = []
    occurrence_counts: list[int] = []
    for slot_index, slot in enumerate(canonical_slots):
        sequences = tuple(
            _token_key_sequence(value, case_sensitive=slot.case_sensitive)
            for value in slot.accepted
        )
        if len(set(sequences)) != len(sequences):
            raise ValueError(
                f"critical slot {slot.id!r} contains duplicate accepted forms"
            )
        _reject_nested_accepted_sequences(slot, sequences)
        intervals = sorted(
            {
                interval
                for sequence in sequences
                for interval in _find_sequence_intervals(
                    recognized_tokens,
                    sequence,
                    case_sensitive=slot.case_sensitive,
                )
            }
        )
        occurrence_counts.append(len(intervals))
        candidates.extend(
            _CandidateInterval(slot_index, start, end) for start, end in intervals
        )

    used_counts = _select_maximum_non_overlapping_intervals(
        canonical_slots,
        tuple(candidates),
    )
    matched_count = sum(used_counts)
    expected_count = sum(slot.count for slot in canonical_slots)
    missing_slot_ids = tuple(
        slot.id
        for slot, used_count in zip(canonical_slots, used_counts, strict=True)
        for _ in range(slot.count - used_count)
    )
    duplicate_occurrence_count = sum(
        max(0, occurrence_count - slot.count)
        for slot, occurrence_count in zip(
            canonical_slots, occurrence_counts, strict=True
        )
    )
    return CriticalSlotScore(
        accuracy=RationalScore(matched_count, expected_count),
        missing_slot_ids=missing_slot_ids,
        duplicate_occurrence_count=duplicate_occurrence_count,
    )


def _validate_and_sort_slots(
    expected: tuple[ExpectedCriticalSlot, ...],
) -> tuple[ExpectedCriticalSlot, ...]:
    if type(expected) is not tuple or not expected:
        raise ValueError("expected critical slots must be a non-empty tuple")
    if any(not isinstance(slot, ExpectedCriticalSlot) for slot in expected):
        raise TypeError("expected tuple contains a non-ExpectedCriticalSlot value")
    ids = [slot.id for slot in expected]
    if len(ids) != len(set(ids)):
        raise ValueError("critical slot ids must be unique")
    return tuple(sorted(expected, key=lambda slot: slot.id))


def _token_key_sequence(
    value: str,
    *,
    case_sensitive: bool,
) -> tuple[tuple[str, str], ...]:
    tokens = tokenize_content_units(value)
    if not tokens:
        raise ValueError("critical slot form must contain at least one scored token")
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


def _reject_nested_accepted_sequences(
    slot: ExpectedCriticalSlot,
    sequences: tuple[tuple[tuple[str, str], ...], ...],
) -> None:
    for left_index, left in enumerate(sequences):
        for right in sequences[left_index + 1 :]:
            shorter, longer = sorted((left, right), key=len)
            if any(
                longer[offset : offset + len(shorter)] == shorter
                for offset in range(len(longer) - len(shorter) + 1)
            ):
                raise ValueError(
                    f"critical slot {slot.id!r} contains nested accepted forms"
                )


def _select_maximum_non_overlapping_intervals(
    slots: tuple[ExpectedCriticalSlot, ...],
    candidates: tuple[_CandidateInterval, ...],
) -> tuple[int, ...]:
    """Return per-slot use counts with stable lexicographic tie-breaking."""

    zero_counts = (0,) * len(slots)
    # For one use-count vector, a schedule ending earlier dominates every later
    # schedule because future candidates depend only on the last occupied token.
    states: dict[
        tuple[int, ...],
        tuple[int, tuple[_CandidateInterval, ...]],
    ] = {zero_counts: (0, ())}
    ordered_candidates = sorted(
        candidates,
        key=lambda candidate: (
            candidate.end,
            candidate.start,
            slots[candidate.slot_index].id,
        ),
    )
    for candidate in ordered_candidates:
        for used_counts, (last_end, selected) in tuple(states.items()):
            if last_end > candidate.start:
                continue
            slot_index = candidate.slot_index
            if used_counts[slot_index] >= slots[slot_index].count:
                continue
            updated_counts = list(used_counts)
            updated_counts[slot_index] += 1
            updated_key = tuple(updated_counts)
            updated_schedule = (candidate.end, (*selected, candidate))
            current_schedule = states.get(updated_key)
            if current_schedule is None or _schedule_precedes(
                updated_schedule,
                current_schedule,
                slots,
            ):
                states[updated_key] = updated_schedule

    return max(states, key=lambda counts: (sum(counts), counts))


def _schedule_precedes(
    left: tuple[int, tuple[_CandidateInterval, ...]],
    right: tuple[int, tuple[_CandidateInterval, ...]],
    slots: tuple[ExpectedCriticalSlot, ...],
) -> bool:
    if left[0] != right[0]:
        return left[0] < right[0]
    return _schedule_key(left[1], slots) < _schedule_key(right[1], slots)


def _schedule_key(
    selected: tuple[_CandidateInterval, ...],
    slots: tuple[ExpectedCriticalSlot, ...],
) -> tuple[tuple[int, int, str], ...]:
    return tuple(
        (candidate.start, candidate.end, slots[candidate.slot_index].id)
        for candidate in selected
    )
