"""Score required recall while allowing source-declared optional content."""

from __future__ import annotations

from quality_lab.calculate_token_metrics import (
    ExpectedContentUnit,
    TokenMetricCounts,
    calculate_token_metrics,
)
from quality_lab.tokenize_content_units import ContentToken


def calculate_token_metrics_with_optional_content(
    required: tuple[ExpectedContentUnit, ...],
    precision_truth: tuple[ExpectedContentUnit, ...],
    recognized: tuple[ContentToken, ...],
) -> TokenMetricCounts:
    """Use required truth for recall and all visible truth for precision.

    ``precision_truth`` is the counted union of required and optional source
    content. Optional content therefore never hurts recall when absent, but a
    recognized optional token is not mislabeled as an invention.
    """

    _require_precision_truth_contains_required(required, precision_truth)
    required_score = calculate_token_metrics(required, recognized)
    precision_score = calculate_token_metrics(precision_truth, recognized)
    return TokenMetricCounts(
        recall=required_score.recall,
        precision=precision_score.precision,
        critical_accuracy=required_score.critical_accuracy,
        unmatched_recognized_indexes=precision_score.unmatched_recognized_indexes,
        unexpected_critical_indexes=precision_score.unexpected_critical_indexes,
    )


def _require_precision_truth_contains_required(
    required: tuple[ExpectedContentUnit, ...],
    precision_truth: tuple[ExpectedContentUnit, ...],
) -> None:
    required_counts = _expectation_counts(required)
    precision_counts = _expectation_counts(precision_truth)
    if any(
        precision_counts.get(key, 0) < count
        for key, count in required_counts.items()
    ):
        raise ValueError("precision truth must contain every required occurrence")


def _expectation_counts(
    values: tuple[ExpectedContentUnit, ...],
) -> dict[tuple[str, tuple[str, ...], bool, bool], int]:
    if type(values) is not tuple:
        raise TypeError("expectation values must be an exact tuple")
    result: dict[tuple[str, tuple[str, ...], bool, bool], int] = {}
    for value in values:
        if not isinstance(value, ExpectedContentUnit):
            raise TypeError("expectation tuple contains a non-ExpectedContentUnit value")
        key = (value.kind, value.accepted, value.case_sensitive, value.critical)
        result[key] = result.get(key, 0) + value.count
    return result
