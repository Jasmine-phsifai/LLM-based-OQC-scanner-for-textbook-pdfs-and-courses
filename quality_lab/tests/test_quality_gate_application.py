import pytest

from quality_lab.assert_quality_thresholds import (
    assert_quality_thresholds,
    quality_threshold_failures,
)
from quality_lab.calculate_language_token_metrics import LanguageTokenMetrics
from quality_lab.calculate_token_metrics import (
    ExpectedContentUnit,
    TokenMetricCounts,
    tokenize_and_calculate_metrics,
)
from quality_lab.rational_score import RationalScore
from quality_lab.score_critical_slots import CriticalSlotScore
from quality_lab.score_formula_signatures import (
    ExpectedFormula,
    FormulaScore,
    score_formula_signatures,
)
from quality_lab.score_ordered_anchors import OrderedAnchorScore
from quality_lab.score_table_cells import TableScore


def _text_score(
    *,
    recall=RationalScore(95, 100),
    precision=RationalScore(90, 100),
    critical=RationalScore(1, 1),
    unexpected=(),
):
    return TokenMetricCounts(recall, precision, critical, unexpected, unexpected)


def _critical_slot_score():
    return CriticalSlotScore(RationalScore(1, 1), (), 0)


def _language_scores(languages=("en-US", "zh-CN")):
    return tuple(LanguageTokenMetrics(language, _text_score()) for language in languages)


def test_printed_text_accepts_exact_thresholds_and_rejects_one_below():
    assert_quality_thresholds(
        "printed_slide",
        text=_text_score(),
        language_text=_language_scores(),
        critical_slots=_critical_slot_score(),
    )
    with pytest.raises(AssertionError, match="text recall is below threshold"):
        assert_quality_thresholds(
            "printed_slide",
            text=_text_score(recall=RationalScore(94, 100)),
            language_text=_language_scores(),
            critical_slots=_critical_slot_score(),
        )


def test_each_declared_language_must_pass_even_when_aggregate_recall_passes():
    aggregate = _text_score(
        recall=RationalScore(302, 312),
        precision=RationalScore(1, 1),
    )
    language_scores = (
        LanguageTokenMetrics("en-US", _text_score(recall=RationalScore(1, 1))),
        LanguageTokenMetrics(
            "zh-CN",
            _text_score(recall=RationalScore(166, 176)),
        ),
    )

    with pytest.raises(AssertionError, match="zh-CN text recall is below threshold"):
        assert_quality_thresholds(
            "printed_slide",
            text=aggregate,
            language_text=language_scores,
            critical_slots=_critical_slot_score(),
        )


def test_manifest_fixture_class_requires_critical_slots_without_caller_opt_in():
    with pytest.raises(AssertionError, match="critical-slot score is required"):
        assert_quality_thresholds(
            "printed_slide",
            text=_text_score(),
            language_text=_language_scores(),
        )


def test_unexpected_critical_text_unit_is_a_hard_failure_above_thresholds():
    with pytest.raises(AssertionError, match="unexpected critical units"):
        assert_quality_thresholds(
            "printed_slide",
            text=_text_score(
                recall=RationalScore(1, 1),
                precision=RationalScore(1, 1),
                unexpected=(4,),
            ),
            language_text=_language_scores(),
            critical_slots=_critical_slot_score(),
        )


def test_number_is_automatically_critical_even_when_annotation_omits_the_flag():
    expected = (
        ExpectedContentUnit("prose", "word", ("echo",), count=99),
        ExpectedContentUnit("number", "number", ("7",)),
    )
    score = tokenize_and_calculate_metrics(expected, " ".join(("echo",) * 99))
    assert score.recall == RationalScore(99, 100)
    assert score.critical_accuracy == RationalScore(0, 1)
    with pytest.raises(AssertionError, match="critical accuracy"):
        assert_quality_thresholds(
            "printed_slide",
            text=score,
            language_text=_language_scores(),
            critical_slots=_critical_slot_score(),
        )


def test_formula_board_applies_text_formula_and_insertion_gates_together():
    passing_formula = FormulaScore(
        RationalScore(9, 10),
        RationalScore(9, 10),
        RationalScore(1, 1),
        (),
        (),
        1,
        0,
    )
    assert_quality_thresholds(
        "formula_board",
        text=_text_score(),
        language_text=_language_scores(),
        critical_slots=_critical_slot_score(),
        formulas=passing_formula,
    )
    inserted = FormulaScore(
        passing_formula.signature_accuracy,
        passing_formula.atom_precision,
        passing_formula.critical_accuracy,
        (),
        ("F99",),
        0,
        3,
    )
    with pytest.raises(AssertionError, match="unexpected labels.*unexpected atoms"):
        assert_quality_thresholds(
            "formula_board",
            text=_text_score(),
            language_text=_language_scores(),
            critical_slots=_critical_slot_score(),
            formulas=inserted,
        )


def test_one_fraction_structure_loss_cannot_hide_at_the_ninety_percent_floor():
    expected = (ExpectedFormula("F00", (r"\frac{a}{b}",)),) + tuple(
        ExpectedFormula(f"F{index:02d}", (f"x_{index}=1",))
        for index in range(1, 10)
    )
    recognized = "\n".join(
        ("F00: $a b$",)
        + tuple(f"F{index:02d}: $x_{index}=1$" for index in range(1, 10))
    )
    formula_score = score_formula_signatures(expected, recognized)
    assert formula_score.signature_accuracy == RationalScore(9, 10)
    with pytest.raises(AssertionError, match="formula critical accuracy"):
        assert_quality_thresholds(
            "formula_board",
            text=_text_score(),
            language_text=_language_scores(),
            critical_slots=_critical_slot_score(),
            formulas=formula_score,
        )


def test_table_requires_accuracy_exact_headers_critical_values_and_no_extra_coordinates():
    passing = TableScore(
        RationalScore(2, 2),
        RationalScore(19, 20),
        RationalScore(1, 1),
        0,
    )
    assert_quality_thresholds(
        "table",
        text=_text_score(),
        language_text=_language_scores(),
        table=passing,
    )
    extra = TableScore(
        passing.header_accuracy,
        passing.data_cell_accuracy,
        passing.critical_accuracy,
        1,
    )
    with pytest.raises(AssertionError, match="unexpected data coordinates"):
        assert_quality_thresholds(
            "table",
            text=_text_score(),
            language_text=_language_scores(),
            table=extra,
        )


def test_unexpected_numeric_table_content_is_a_hard_failure_above_accuracy_gate():
    score = TableScore(
        RationalScore(2, 2),
        RationalScore(39, 40),
        RationalScore(1, 1),
        0,
        1,
    )
    with pytest.raises(AssertionError, match="unexpected critical cell content"):
        assert_quality_thresholds(
            "table",
            text=_text_score(),
            language_text=_language_scores(),
            table=score,
        )


def test_table_residual_text_cannot_hide_hallucinated_prose():
    passing_table = TableScore(
        RationalScore(1, 1),
        RationalScore(1, 1),
        RationalScore(1, 1),
        0,
    )
    with pytest.raises(AssertionError, match="content precision"):
        assert_quality_thresholds(
            "table",
            text=_text_score(precision=RationalScore(89, 100)),
            language_text=_language_scores(),
            table=passing_table,
        )


def test_ordered_request_requires_all_order_and_source_metadata_gates():
    passing = OrderedAnchorScore(
        RationalScore(2, 2),
        (0, 5),
        True,
        True,
        True,
        True,
        0,
    )
    passing_formula = FormulaScore(
        RationalScore(1, 1),
        RationalScore(1, 1),
        RationalScore(1, 1),
        (),
        (),
        0,
        0,
    )
    assert_quality_thresholds(
        "ordered_request",
        text=_text_score(),
        language_text=_language_scores(),
        critical_slots=_critical_slot_score(),
        formulas=passing_formula,
        anchors=passing,
    )
    failing = OrderedAnchorScore(
        passing.presence,
        passing.first_token_offsets,
        False,
        True,
        True,
        True,
        0,
    )
    with pytest.raises(AssertionError, match="ordered-anchor hard gate"):
        assert_quality_thresholds(
            "ordered_request",
            text=_text_score(),
            language_text=_language_scores(),
            critical_slots=_critical_slot_score(),
            formulas=passing_formula,
            anchors=failing,
        )

    inserted_formula = FormulaScore(
        passing_formula.signature_accuracy,
        passing_formula.atom_precision,
        passing_formula.critical_accuracy,
        (),
        ("F99",),
        0,
        1,
    )
    with pytest.raises(AssertionError, match="unexpected labels.*unexpected atoms"):
        assert_quality_thresholds(
            "ordered_request",
            text=_text_score(),
            language_text=_language_scores(),
            critical_slots=_critical_slot_score(),
            formulas=inserted_formula,
            anchors=passing,
        )


def test_missing_required_channel_and_unknown_fixture_class_fail_closed():
    with pytest.raises(AssertionError, match="text score is required"):
        assert_quality_thresholds("handwriting")
    with pytest.raises(ValueError, match="unknown Phase 1 fixture class"):
        assert_quality_thresholds("future_fixture")


@pytest.mark.parametrize(
    ("fixture_class", "channel", "score", "failure_code"),
    (
        *(
            (fixture_class, "formulas", FormulaScore(
                RationalScore(1, 1), RationalScore(1, 1), RationalScore(1, 1),
                (), (), 0, 0,
            ), "formula_score_not_applicable")
            for fixture_class in (
                "printed_slide", "degraded_printed_slide", "handwriting", "table"
            )
        ),
        *(
            (fixture_class, "table", TableScore(
                RationalScore(1, 1), RationalScore(1, 1), RationalScore(1, 1), 0,
            ), "table_score_not_applicable")
            for fixture_class in (
                "printed_slide", "degraded_printed_slide", "handwriting",
                "formula_board", "ordered_request",
            )
        ),
        *(
            (fixture_class, "anchors", OrderedAnchorScore(
                RationalScore(1, 1), (0,), True, True, True, True, 0,
            ), "ordered_anchor_score_not_applicable")
            for fixture_class in (
                "printed_slide", "degraded_printed_slide", "handwriting",
                "formula_board", "table",
            )
        ),
        (
            "table",
            "critical_slots",
            CriticalSlotScore(RationalScore(1, 1), (), 0),
            "critical_slot_score_not_applicable",
        ),
    ),
)
def test_non_applicable_typed_channels_fail_closed(
    fixture_class,
    channel,
    score,
    failure_code,
):
    failures = quality_threshold_failures(fixture_class, **{channel: score})

    assert failure_code in failures


def test_multiple_non_applicable_channels_have_one_exact_failure_order():
    failures = quality_threshold_failures(
        "printed_slide",
        text=_text_score(),
        language_text=_language_scores(),
        critical_slots=_critical_slot_score(),
        formulas=FormulaScore(
            RationalScore(1, 1),
            RationalScore(1, 1),
            RationalScore(1, 1),
            (),
            (),
            0,
            0,
        ),
        table=TableScore(
            RationalScore(1, 1),
            RationalScore(1, 1),
            RationalScore(1, 1),
            0,
        ),
        anchors=OrderedAnchorScore(
            RationalScore(1, 1),
            (0,),
            True,
            True,
            True,
            True,
            0,
        ),
    )

    assert failures == (
        "formula_score_not_applicable",
        "table_score_not_applicable",
        "ordered_anchor_score_not_applicable",
    )


@pytest.mark.parametrize(
    ("fixture_class", "channel"),
    (
        ("table", "critical_slots"),
        ("printed_slide", "formulas"),
        ("printed_slide", "table"),
        ("printed_slide", "anchors"),
    ),
)
def test_wrong_typed_non_applicable_channels_raise_before_thresholds(
    fixture_class,
    channel,
):
    with pytest.raises(TypeError, match="exact"):
        quality_threshold_failures(fixture_class, **{channel: object()})
