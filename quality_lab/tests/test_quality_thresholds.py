from types import MappingProxyType

import pytest

from quality_lab.phase1_quality_thresholds import QUALITY_THRESHOLDS
from quality_lab.rational_score import RationalScore


def test_fixture_thresholds_are_immutable_and_fixed_per_channel():
    assert isinstance(QUALITY_THRESHOLDS, MappingProxyType)
    assert QUALITY_THRESHOLDS["printed_slide"].text_recall == RationalScore(95, 100)
    assert QUALITY_THRESHOLDS["printed_slide"].content_precision == RationalScore(90, 100)
    assert QUALITY_THRESHOLDS["printed_slide"].critical_slots_required
    assert QUALITY_THRESHOLDS["printed_slide"].languages == ("en-US", "zh-CN")
    assert QUALITY_THRESHOLDS["handwriting"].text_recall == RationalScore(85, 100)
    assert QUALITY_THRESHOLDS["formula_board"].formula_signature_accuracy == RationalScore(90, 100)
    assert QUALITY_THRESHOLDS["table"].text_recall == RationalScore(95, 100)
    assert QUALITY_THRESHOLDS["table"].content_precision == RationalScore(90, 100)
    assert QUALITY_THRESHOLDS["table"].table_data_accuracy == RationalScore(95, 100)
    assert QUALITY_THRESHOLDS["table"].exact_table_headers
    assert QUALITY_THRESHOLDS["ordered_request"].ordered_anchors_required
    assert QUALITY_THRESHOLDS["ordered_request"].critical_slots_required
    assert QUALITY_THRESHOLDS["ordered_request"].languages == ("en-US", "zh-CN")
    assert QUALITY_THRESHOLDS["ordered_request"].formula_signature_accuracy == RationalScore(90, 100)


@pytest.mark.parametrize("threshold_percent", (85, 90, 95))
def test_rational_gate_rejects_one_below_accepts_exactly_at_and_one_above(
    threshold_percent,
):
    threshold = RationalScore(threshold_percent, 100)
    assert not RationalScore(threshold_percent - 1, 100).meets(threshold)
    assert RationalScore(threshold_percent, 100).meets(threshold)
    assert RationalScore(threshold_percent + 1, 100).meets(threshold)


def test_perfect_critical_gate_rejects_one_below_and_accepts_exact():
    threshold = RationalScore(1, 1)
    assert not RationalScore(99, 100).meets(threshold)
    assert RationalScore(1, 1).meets(threshold)


@pytest.mark.parametrize(
    "numerator,denominator",
    ((-1, 1), (2, 1), (0, 0)),
)
def test_invalid_rational_counts_are_rejected(numerator, denominator):
    with pytest.raises(ValueError):
        RationalScore(numerator, denominator)
