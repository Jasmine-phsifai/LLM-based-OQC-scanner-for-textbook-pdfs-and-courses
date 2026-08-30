import pytest

from quality_lab.assert_quality_thresholds import (
    assert_quality_thresholds,
    quality_threshold_failures,
)
from quality_lab.calculate_language_token_metrics import LanguageTokenMetrics
from quality_lab.calculate_token_metrics import TokenMetricCounts
from quality_lab.rational_score import RationalScore
from quality_lab.score_critical_slots import (
    CriticalSlotScore,
    ExpectedCriticalSlot,
    score_critical_slots,
)


CRITICAL_SLOTS = (
    ExpectedCriticalSlot("course-id", ("COURSE-ID: QCR-204",)),
    ExpectedCriticalSlot("revision-date", ("REVISION: 2026-07-10",)),
    ExpectedCriticalSlot("table-total", ("TABLE TOTAL: 128.75 kg",)),
)


def _passing_text_score() -> TokenMetricCounts:
    return TokenMetricCounts(
        RationalScore(1, 1),
        RationalScore(1, 1),
        RationalScore(1, 1),
        (),
        (),
    )


def _passing_language_scores(
    *languages: str,
) -> tuple[LanguageTokenMetrics, ...]:
    return tuple(
        LanguageTokenMetrics(language, _passing_text_score())
        for language in languages
    )


def test_identifier_date_and_unit_slots_match_only_as_full_token_sequences():
    score = score_critical_slots(
        CRITICAL_SLOTS,
        (
            "COURSE-ID: QCR-204\n"
            "REVISION: 2026-07-10\n"
            "TABLE TOTAL: 128.75 kg"
        ),
    )

    assert score.accuracy == RationalScore(3, 3)
    assert score.missing_slot_ids == ()
    assert score.duplicate_occurrence_count == 0
    assert score.passes


def test_components_split_by_unrelated_tokens_do_not_reassemble_into_slots():
    score = score_critical_slots(
        CRITICAL_SLOTS,
        (
            "COURSE-ID: QCR note - 204\n"
            "REVISION: 2026 release - 07 - 10\n"
            "TABLE TOTAL: 128.75 approximate kg"
        ),
    )

    assert score.accuracy == RationalScore(0, 3)
    assert score.missing_slot_ids == (
        "course-id",
        "revision-date",
        "table-total",
    )
    assert not score.passes


def test_substring_spoof_does_not_match_a_full_identifier_token():
    expected = (ExpectedCriticalSlot("course-id", ("QCR-204",)),)

    score = score_critical_slots(expected, "XQCR-204")

    assert score.accuracy == RationalScore(0, 1)
    assert score.missing_slot_ids == ("course-id",)


def test_declared_count_uses_distinct_occurrences_and_reports_duplicates():
    expected = (ExpectedCriticalSlot("course-id", ("QCR-204",), count=2),)

    score = score_critical_slots(expected, "QCR-204 QCR-204 QCR-204")

    assert score.accuracy == RationalScore(2, 2)
    assert score.missing_slot_ids == ()
    assert score.duplicate_occurrence_count == 1
    assert not score.passes


def test_case_insensitive_accepted_alternatives_remain_full_sequences():
    expected = (
        ExpectedCriticalSlot(
            "course-id",
            ("QCR-204", "COURSE-204"),
            case_sensitive=False,
        ),
    )

    assert score_critical_slots(expected, "qcr-204").passes


def test_overlapping_slots_cannot_reuse_the_shared_recognized_token():
    expected = (
        ExpectedCriticalSlot("first", ("ALPHA BETA",)),
        ExpectedCriticalSlot("second", ("BETA GAMMA",)),
    )

    overlapping = score_critical_slots(expected, "ALPHA BETA GAMMA")
    reversed_manifest_order = score_critical_slots(
        tuple(reversed(expected)),
        "ALPHA BETA GAMMA",
    )
    separate = score_critical_slots(expected, "ALPHA BETA BETA GAMMA")

    assert overlapping.accuracy == RationalScore(1, 2)
    assert overlapping.missing_slot_ids == ("second",)
    assert reversed_manifest_order == overlapping
    assert separate.accuracy == RationalScore(2, 2)
    assert separate.passes


def test_equivalent_accepted_forms_and_duplicate_slot_ids_fail_closed():
    equivalent_forms = (
        ExpectedCriticalSlot("course-id", ("QCR-204", "QCR - 204")),
    )
    with pytest.raises(ValueError, match="duplicate accepted forms"):
        score_critical_slots(equivalent_forms, "QCR-204")

    nested_forms = (
        ExpectedCriticalSlot("course-id", ("QCR", "QCR-204")),
    )
    with pytest.raises(ValueError, match="nested accepted forms"):
        score_critical_slots(nested_forms, "QCR-204")

    duplicate_ids = (
        ExpectedCriticalSlot("same", ("ALPHA",)),
        ExpectedCriticalSlot("same", ("BETA",)),
    )
    with pytest.raises(ValueError, match="ids must be unique"):
        score_critical_slots(duplicate_ids, "ALPHA BETA")


def test_threshold_api_returns_stable_critical_slot_failure_codes():
    missing = CriticalSlotScore(RationalScore(0, 1), ("course-id",), 0)
    duplicated = CriticalSlotScore(RationalScore(1, 1), (), 1)

    assert quality_threshold_failures(
        "printed_slide",
        text=_passing_text_score(),
        language_text=_passing_language_scores("en-US", "zh-CN"),
        critical_slots=missing,
    ) == ("critical_slot_accuracy_below_one",)
    assert quality_threshold_failures(
        "printed_slide",
        text=_passing_text_score(),
        language_text=_passing_language_scores("en-US", "zh-CN"),
        critical_slots=duplicated,
    ) == ("critical_slot_duplicate_occurrences",)
    assert quality_threshold_failures(
        "printed_slide",
        text=_passing_text_score(),
        language_text=_passing_language_scores("en-US", "zh-CN"),
    ) == ("critical_slot_score_required",)


def test_threshold_api_returns_stable_codes_for_existing_channel_gates():
    failing_text = TokenMetricCounts(
        RationalScore(94, 100),
        RationalScore(89, 100),
        RationalScore(0, 1),
        (4,),
        (4,),
    )

    assert quality_threshold_failures(
        "printed_slide",
        text=failing_text,
        language_text=_passing_language_scores("en-US", "zh-CN"),
        critical_slots=CriticalSlotScore(RationalScore(1, 1), (), 0),
    ) == (
        "text_recall_below_threshold",
        "content_precision_below_threshold",
        "text_critical_accuracy_below_one",
        "text_unexpected_critical_units",
    )
    assert quality_threshold_failures("handwriting") == (
        "text_score_required",
        "language_text_scores_required",
        "critical_slot_score_required",
    )
    assert quality_threshold_failures(
        "formula_board",
        text=_passing_text_score(),
        language_text=_passing_language_scores("en-US", "zh-CN"),
        critical_slots=CriticalSlotScore(RationalScore(1, 1), (), 0),
    ) == ("formula_score_required",)
    assert quality_threshold_failures("table") == (
        "text_score_required",
        "language_text_scores_required",
        "table_score_required",
    )
    assert quality_threshold_failures("ordered_request") == (
        "text_score_required",
        "language_text_scores_required",
        "critical_slot_score_required",
        "formula_score_required",
        "ordered_anchor_score_required",
    )


def test_assertion_wrapper_preserves_messages_for_critical_slot_failures():
    score = CriticalSlotScore(RationalScore(0, 1), ("course-id",), 1)

    with pytest.raises(
        AssertionError,
        match=(
            "critical-slot accuracy is below 1.00; "
            "critical slots contain duplicate occurrences"
        ),
    ):
        assert_quality_thresholds(
            "printed_slide",
            text=_passing_text_score(),
            language_text=_passing_language_scores("en-US", "zh-CN"),
            critical_slots=score,
        )


def test_critical_slot_score_rejects_inconsistent_missing_id_evidence():
    with pytest.raises(ValueError, match="must match the accuracy counts"):
        CriticalSlotScore(RationalScore(1, 2), (), 0)
