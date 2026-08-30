import pytest

from quality_lab.calculate_token_metrics import (
    ExpectedContentUnit,
    tokenize_and_calculate_metrics,
)
from quality_lab.rational_score import RationalScore


EXPECTED_TEXT = (
    ExpectedContentUnit("title", "word", ("Optimization",)),
    ExpectedContentUnit("han-you", "han", ("优",)),
    ExpectedContentUnit("han-hua", "han", ("化",)),
    ExpectedContentUnit("value", "number", ("47.25",), critical=True),
    ExpectedContentUnit("relation", "relation", ("≤",), critical=True),
    ExpectedContentUnit("limit", "number", ("50",), critical=True),
)


def test_token_metrics_use_exact_one_to_one_counts():
    score = tokenize_and_calculate_metrics(
        EXPECTED_TEXT, "Optimization 优化 47.25 ≤ 50"
    )
    assert score.recall == RationalScore(6, 6)
    assert score.precision == RationalScore(6, 6)
    assert score.critical_accuracy == RationalScore(3, 3)
    assert score.unmatched_recognized_indexes == ()
    assert score.unexpected_critical_indexes == ()


def test_duplicate_prose_lowers_precision_without_increasing_recall():
    score = tokenize_and_calculate_metrics(
        EXPECTED_TEXT, "Optimization Optimization 优化 47.25 ≤ 50"
    )
    assert score.recall == RationalScore(6, 6)
    assert score.precision == RationalScore(6, 7)
    assert len(score.unmatched_recognized_indexes) == 1
    assert score.unexpected_critical_indexes == ()


@pytest.mark.parametrize(
    "recognized",
    (
        "Optimization 优化 47.26 ≤ 50",
        "Optimization 优化 47.25 < 50",
        "Optimization 优化 47.25 ≤ - 50",
    ),
)
def test_digit_relation_and_sign_corruptions_are_hard_critical_insertions(recognized):
    score = tokenize_and_calculate_metrics(EXPECTED_TEXT, recognized)
    assert score.critical_accuracy.numerator < score.critical_accuracy.denominator or (
        score.unexpected_critical_indexes
    )
    assert score.unexpected_critical_indexes


def test_substring_and_case_changes_do_not_satisfy_a_case_sensitive_word():
    substring = tokenize_and_calculate_metrics(EXPECTED_TEXT, "OptimizationX 优化 47.25 ≤ 50")
    changed_case = tokenize_and_calculate_metrics(EXPECTED_TEXT, "optimization 优化 47.25 ≤ 50")
    assert substring.recall == RationalScore(5, 6)
    assert changed_case.recall == RationalScore(5, 6)


def test_ambiguous_expected_spellings_are_rejected():
    ambiguous = (
        ExpectedContentUnit("first", "word", ("Alpha",), case_sensitive=False),
        ExpectedContentUnit("second", "word", ("alpha",)),
    )
    with pytest.raises(ValueError, match="ambiguous accepted spellings"):
        tokenize_and_calculate_metrics(ambiguous, "alpha")


def test_expected_counts_are_expanded_without_reusing_recognized_occurrences():
    expected = (ExpectedContentUnit("repeat", "word", ("echo",), count=2),)
    score = tokenize_and_calculate_metrics(expected, "echo")
    assert score.recall == RationalScore(1, 2)
    assert score.precision == RationalScore(1, 1)


def test_units_are_scored_and_unexpected_units_are_critical_insertions():
    expected = (
        ExpectedContentUnit("target", "word", ("TARGET",)),
        ExpectedContentUnit("value", "number", ("95",)),
        ExpectedContentUnit("percent", "unit", ("%",)),
    )
    passing = tokenize_and_calculate_metrics(expected, "TARGET 95%")
    assert passing.critical_accuracy == RationalScore(2, 2)
    assert passing.unexpected_critical_indexes == ()

    inserted = tokenize_and_calculate_metrics(expected, "TARGET 95% °")
    assert inserted.unexpected_critical_indexes
