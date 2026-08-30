"""Tests for required-recall and source-complete precision semantics."""

import pytest

from quality_lab.calculate_language_token_metrics_with_optional_content import (
    calculate_language_token_metrics_with_optional_content,
)
from quality_lab.calculate_token_metrics import ExpectedContentUnit
from quality_lab.calculate_token_metrics_with_optional_content import (
    calculate_token_metrics_with_optional_content,
)
from quality_lab.tokenize_content_units import tokenize_content_units


def _unit(identifier, kind, value, *, count=1):
    return ExpectedContentUnit(
        id=identifier,
        kind=kind,
        accepted=(value,),
        count=count,
        case_sensitive=True,
    )


def test_optional_source_content_improves_precision_without_changing_recall():
    required = (_unit("required", "word", "Main"),)
    precision_truth = required + (_unit("faint", "word", "ATCG"),)

    complete = calculate_token_metrics_with_optional_content(
        required,
        precision_truth,
        tokenize_content_units("Main ATCG"),
    )
    required_only = calculate_token_metrics_with_optional_content(
        required,
        precision_truth,
        tokenize_content_units("Main"),
    )
    optional_only = calculate_token_metrics_with_optional_content(
        required,
        precision_truth,
        tokenize_content_units("ATCG"),
    )

    assert (complete.recall.numerator, complete.recall.denominator) == (1, 1)
    assert (complete.precision.numerator, complete.precision.denominator) == (2, 2)
    assert (required_only.recall.numerator, required_only.recall.denominator) == (1, 1)
    assert (required_only.precision.numerator, required_only.precision.denominator) == (1, 1)
    assert (optional_only.recall.numerator, optional_only.recall.denominator) == (0, 1)
    assert (optional_only.precision.numerator, optional_only.precision.denominator) == (1, 1)


def test_optional_critical_source_token_is_allowed_but_invention_is_not():
    required = (_unit("required", "word", "Ratio"),)
    precision_truth = required + (_unit("faint-number", "number", "5"),)

    source_number = calculate_token_metrics_with_optional_content(
        required,
        precision_truth,
        tokenize_content_units("Ratio 5"),
    )
    invention = calculate_token_metrics_with_optional_content(
        required,
        precision_truth,
        tokenize_content_units("Ratio 9"),
    )

    assert source_number.unexpected_critical_indexes == ()
    assert invention.unexpected_critical_indexes == (1,)


def test_precision_truth_must_contain_required_occurrences():
    required = (_unit("required", "word", "Main", count=2),)
    incomplete_precision_truth = (_unit("precision", "word", "Main"),)

    with pytest.raises(ValueError, match="every required occurrence"):
        calculate_token_metrics_with_optional_content(
            required,
            incomplete_precision_truth,
            tokenize_content_units("Main"),
        )


def test_language_projection_uses_required_recall_and_optional_precision():
    required = (_unit("required", "word", "Main"),)
    precision_truth = required + (_unit("faint", "word", "ATCG"),)

    (english,) = calculate_language_token_metrics_with_optional_content(
        required,
        precision_truth,
        tokenize_content_units("Main ATCG"),
        ("en-US",),
    )

    assert (english.metrics.recall.numerator, english.metrics.recall.denominator) == (1, 1)
    assert (english.metrics.precision.numerator, english.metrics.precision.denominator) == (2, 2)
