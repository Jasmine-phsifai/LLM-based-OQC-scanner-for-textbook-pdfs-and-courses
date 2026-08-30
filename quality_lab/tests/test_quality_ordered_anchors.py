import pytest

from quality_lab.rational_score import RationalScore
from quality_lab.score_ordered_anchors import OrderedAnchor, score_ordered_anchors


ANCHORS = (
    OrderedAnchor("image-zero", 0, ("SLIDE-A-BEGIN",)),
    OrderedAnchor("image-one", 1, ("BOARD-B-BEGIN",)),
)


def _score(text, *, source_indices=(0, 1), image_count=2):
    return score_ordered_anchors(
        ANCHORS,
        text,
        actual_source_indices=source_indices,
        actual_image_count=image_count,
    )


def test_full_token_anchors_pass_in_source_order():
    score = _score("SLIDE-A-BEGIN content then BOARD-B-BEGIN")
    assert score.presence == RationalScore(2, 2)
    assert score.first_token_offsets[0] < score.first_token_offsets[1]
    assert score.duplicate_occurrence_count == 0
    assert score.passes


def test_swapped_first_appearances_fail_even_when_both_anchors_exist():
    score = _score("BOARD-B-BEGIN then SLIDE-A-BEGIN")
    assert score.presence == RationalScore(2, 2)
    assert not score.first_appearances_in_order
    assert not score.passes


def test_duplicate_before_the_expected_first_anchor_uses_earliest_occurrence():
    score = _score("BOARD-B-BEGIN SLIDE-A-BEGIN BOARD-B-BEGIN")
    assert score.duplicate_occurrence_count == 1
    assert not score.first_appearances_in_order


def test_duplicate_after_correct_order_is_a_hard_hallucination_failure():
    score = _score("SLIDE-A-BEGIN BOARD-B-BEGIN SLIDE-A-BEGIN")
    assert score.first_appearances_in_order
    assert score.duplicate_occurrence_count == 1
    assert not score.passes


def test_two_anchors_cannot_reuse_one_overlapping_token_occurrence():
    overlapping = (
        OrderedAnchor("phrase", 0, ("ALPHA BETA",)),
        OrderedAnchor("suffix", 1, ("BETA",)),
    )
    score = score_ordered_anchors(
        overlapping,
        "ALPHA BETA",
        actual_source_indices=(0, 1),
        actual_image_count=2,
    )
    assert score.presence == RationalScore(2, 2)
    assert not score.anchors_do_not_overlap
    assert not score.passes


@pytest.mark.parametrize(
    "text",
    (
        "SLIDE-A-BEGIN only",
        "slide-A-BEGIN then BOARD-B-BEGIN",
        "XSLIDE-A-BEGIN then BOARD-B-BEGIN",
    ),
)
def test_missing_case_changed_and_substring_spoofed_anchors_do_not_pass(text):
    score = _score(text)
    assert score.presence == RationalScore(1, 2)
    assert not score.passes


def test_source_tuple_and_image_count_are_independent_hard_gates():
    text = "SLIDE-A-BEGIN then BOARD-B-BEGIN"
    assert not _score(text, source_indices=(1, 0)).source_order_matches
    assert not _score(text, image_count=1).image_count_matches


def test_ambiguous_anchor_forms_are_rejected():
    ambiguous = (
        OrderedAnchor("first", 0, ("Anchor",), case_sensitive=False),
        OrderedAnchor("second", 1, ("anchor",)),
    )
    with pytest.raises(ValueError, match="ambiguous accepted forms"):
        score_ordered_anchors(
            ambiguous,
            "Anchor anchor",
            actual_source_indices=(0, 1),
            actual_image_count=2,
        )


def test_anchor_source_indexes_must_describe_one_contiguous_source_tuple():
    malformed = (
        OrderedAnchor("first", 0, ("FIRST",)),
        OrderedAnchor("third", 2, ("THIRD",)),
    )
    with pytest.raises(ValueError, match="contiguous"):
        score_ordered_anchors(
            malformed,
            "FIRST THIRD",
            actual_source_indices=(0, 2),
            actual_image_count=3,
        )


def test_multiple_manifest_ordered_anchors_may_describe_one_source():
    anchors = (
        OrderedAnchor("first-start", 0, ("FIRST-START",)),
        OrderedAnchor("first-end", 0, ("FIRST-END",)),
        OrderedAnchor("second-start", 1, ("SECOND-START",)),
    )
    score = score_ordered_anchors(
        anchors,
        "FIRST-START FIRST-END SECOND-START",
        actual_source_indices=(0, 1),
        actual_image_count=2,
    )
    assert score.passes
