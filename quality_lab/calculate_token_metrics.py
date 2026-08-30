"""Calculate one-to-one text recall, precision, and critical counts."""

from __future__ import annotations

from dataclasses import dataclass

from quality_lab.normalize_content_units import normalize_visible_text
from quality_lab.rational_score import PERFECT_SCORE, ZERO_SCORE, RationalScore
from quality_lab.tokenize_content_units import ContentToken, tokenize_content_units


_CRITICAL_INSERTION_KINDS = frozenset(
    {"number", "sign", "relation", "operator", "unit"}
)


@dataclass(frozen=True, slots=True)
class ExpectedContentUnit:
    """A counted content unit and its precommitted accepted spellings."""

    id: str
    kind: str
    accepted: tuple[str, ...]
    count: int = 1
    case_sensitive: bool = True
    critical: bool = False

    def __post_init__(self) -> None:
        if type(self.id) is not str or not self.id:
            raise ValueError("expected content unit id must be a non-empty plain string")
        if self.kind not in {
            "word",
            "han",
            "number",
            "sign",
            "relation",
            "operator",
            "unit",
        }:
            raise ValueError(f"unsupported expected content-unit kind: {self.kind!r}")
        if type(self.accepted) is not tuple or not self.accepted:
            raise ValueError("accepted spellings must be a non-empty tuple")
        if type(self.count) is not int or self.count <= 0:
            raise ValueError("expected content-unit count must be a positive integer")
        if type(self.case_sensitive) is not bool or type(self.critical) is not bool:
            raise TypeError("case_sensitive and critical must be exact booleans")


@dataclass(frozen=True, slots=True)
class TokenMetricCounts:
    """Exact text-channel metrics plus unmatched occurrence evidence."""

    recall: RationalScore
    precision: RationalScore
    critical_accuracy: RationalScore
    unmatched_recognized_indexes: tuple[int, ...]
    unexpected_critical_indexes: tuple[int, ...]


def calculate_token_metrics(
    expected: tuple[ExpectedContentUnit, ...],
    recognized: tuple[ContentToken, ...],
) -> TokenMetricCounts:
    """Match every recognized occurrence to at most one expected occurrence."""

    if type(expected) is not tuple or type(recognized) is not tuple:
        raise TypeError("expected units and recognized tokens must be tuples")
    if any(type(token) is not ContentToken for token in recognized):
        raise TypeError("recognized tuple contains a non-ContentToken value")
    normalized_options = _validate_and_normalize_expectations(expected)
    remaining = [unit.count for unit in expected]
    matched_by_unit = [0 for _ in expected]
    unmatched_recognized: list[int] = []

    for token_index, token in enumerate(recognized):
        matches = [
            unit_index
            for unit_index, unit in enumerate(expected)
            if remaining[unit_index] > 0
            and token.kind == unit.kind
            and _matches(token.value, normalized_options[unit_index], unit.case_sensitive)
        ]
        if len(matches) > 1:
            raise ValueError("recognized unit ambiguously matches multiple expectations")
        if not matches:
            unmatched_recognized.append(token_index)
            continue
        unit_index = matches[0]
        remaining[unit_index] -= 1
        matched_by_unit[unit_index] += 1

    expected_count = sum(unit.count for unit in expected)
    matched_count = sum(matched_by_unit)
    critical_count = sum(unit.count for unit in expected if _is_critical(unit))
    matched_critical_count = sum(
        matched_by_unit[index]
        for index, unit in enumerate(expected)
        if _is_critical(unit)
    )
    unexpected_critical = tuple(
        index
        for index in unmatched_recognized
        if recognized[index].kind in _CRITICAL_INSERTION_KINDS
    )
    return TokenMetricCounts(
        recall=(
            RationalScore(matched_count, expected_count)
            if expected_count
            else PERFECT_SCORE
        ),
        precision=(
            RationalScore(matched_count, len(recognized))
            if recognized
            else ZERO_SCORE
        ),
        critical_accuracy=(
            RationalScore(matched_critical_count, critical_count)
            if critical_count
            else PERFECT_SCORE
        ),
        unmatched_recognized_indexes=tuple(unmatched_recognized),
        unexpected_critical_indexes=unexpected_critical,
    )


def tokenize_and_calculate_metrics(
    expected: tuple[ExpectedContentUnit, ...], recognized_text: str
) -> TokenMetricCounts:
    """Tokenize plain visible text and calculate its exact metrics."""

    return calculate_token_metrics(expected, tokenize_content_units(recognized_text))


def _validate_and_normalize_expectations(
    expected: tuple[ExpectedContentUnit, ...],
) -> tuple[tuple[str, ...], ...]:
    ids: set[str] = set()
    normalized_options: list[tuple[str, ...]] = []
    for unit in expected:
        if not isinstance(unit, ExpectedContentUnit):
            raise TypeError("expected tuple contains a non-ExpectedContentUnit value")
        if unit.id in ids:
            raise ValueError(f"duplicate expected content unit id: {unit.id}")
        ids.add(unit.id)
        options: list[str] = []
        for spelling in unit.accepted:
            normalized = normalize_visible_text(spelling, case_sensitive=unit.case_sensitive)
            tokens = tokenize_content_units(normalized)
            if len(tokens) != 1 or tokens[0].kind != unit.kind:
                raise ValueError(
                    f"accepted spelling for {unit.id!r} must tokenize as one {unit.kind}"
                )
            option = tokens[0].value if unit.case_sensitive else tokens[0].value.casefold()
            if option in options:
                raise ValueError(f"duplicate accepted spelling for {unit.id!r}")
            options.append(option)
        normalized_options.append(tuple(options))

    for left_index, left in enumerate(expected):
        for right_index in range(left_index + 1, len(expected)):
            right = expected[right_index]
            if left.kind != right.kind:
                continue
            for left_value in normalized_options[left_index]:
                for right_value in normalized_options[right_index]:
                    if _options_overlap(left_value, left, right_value, right):
                        raise ValueError(
                            f"ambiguous accepted spellings for {left.id!r} and {right.id!r}"
                        )
    return tuple(normalized_options)


def _matches(value: str, options: tuple[str, ...], case_sensitive: bool) -> bool:
    candidate = value if case_sensitive else value.casefold()
    return candidate in options


def _options_overlap(
    left_value: str,
    left: ExpectedContentUnit,
    right_value: str,
    right: ExpectedContentUnit,
) -> bool:
    if left.case_sensitive and right.case_sensitive:
        return left_value == right_value
    return left_value.casefold() == right_value.casefold()


def _is_critical(unit: ExpectedContentUnit) -> bool:
    return unit.critical or unit.kind in _CRITICAL_INSERTION_KINDS
