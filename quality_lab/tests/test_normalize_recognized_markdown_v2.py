"""Tests for the versioned Phase 1 v2 presentation normalizer."""

import pytest

from quality_lab.build_scoring_views import build_scoring_views
from quality_lab.normalize_recognized_markdown_v2 import (
    normalize_recognized_markdown_v2,
)
from quality_lab.parse_formula_signature import parse_labeled_formulas


FORMULA_RULES = (
    "headings",
    "unordered_list_markers",
    "ordered_list_markers",
    "emphasis",
    "formula_delimiters",
)


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        (r"TARGET RECALL: $\geqslant 95\%$", "TARGET RECALL: ≥ 95%"),
        (r"TARGET RECALL: $\geqslant$ 95%", "TARGET RECALL: ≥ 95%"),
        (r"TARGET RECALL: \(\geq 95\%\)", "TARGET RECALL: ≥ 95%"),
    ),
)
def test_inline_relation_math_becomes_visible_text(source, expected):
    normalized = normalize_recognized_markdown_v2(source)

    assert normalized == expected
    assert build_scoring_views(normalized, neutral_markdown=()).text == expected


def test_missing_colon_and_slanted_relation_canonicalize_without_changing_atoms():
    normalized = normalize_recognized_markdown_v2(
        "\n".join((r"F01 $a_1 + a_2 = 17$", r"F02 $x_1 \leqslant -4$"))
    )

    assert normalized == "\n".join(
        (r"F01: $a_1 + a_2 = 17$", r"F02: $x_1 \leq -4$")
    )
    views = build_scoring_views(normalized, neutral_markdown=FORMULA_RULES)
    assert tuple(item.label for item in parse_labeled_formulas(views.formulas)) == (
        "F01",
        "F02",
    )


def test_strict_paired_formula_table_becomes_independent_labeled_lines():
    source = "\n".join(
        (
            "| | | | |",
            "| --- | --- | --- | --- |",
            r"| **F01** | $P(A | B)=0.625$ | **F07** | $E=mc^2$ |",
            r"| **F02** | $x\leqslant -4$ | **F08** | $y\geqslant 2$ |",
            "ORDER-LAST: ZENITH-926",
        )
    )

    normalized = normalize_recognized_markdown_v2(source)

    assert normalized == "\n".join(
        (
            r"F01: $P(A | B)=0.625$",
            r"F07: $E=mc^2$",
            r"F02: $x\leq -4$",
            r"F08: $y\geq 2$",
            "ORDER-LAST: ZENITH-926",
        )
    )
    views = build_scoring_views(normalized, neutral_markdown=FORMULA_RULES)
    assert views.text == "ORDER-LAST: ZENITH-926"
    assert tuple(item.label for item in parse_labeled_formulas(views.formulas)) == (
        "F01",
        "F07",
        "F02",
        "F08",
    )


@pytest.mark.parametrize(
    ("source", "message"),
    (
        ("TARGET: $95", "unclosed dollar"),
        (r"TARGET: $\sin x$", "relation-only"),
        (r"F01: x=1", "complete math wrapper"),
        (
            "\n".join(
                (
                    "| | | | |",
                    "| --- | --- | --- | --- |",
                    r"| F01 | $x=1$ | F02 | invented |",
                )
            ),
            "strict pairs",
        ),
        (
            "\n".join(
                (
                    "| | | | |",
                    "| --- | --- | --- | --- |",
                    r"| F01 | $x=1$ | F01 | $x=1$ |",
                )
            ),
            "duplicate formula label",
        ),
    ),
)
def test_undeclared_or_ambiguous_presentations_fail_closed(source, message):
    with pytest.raises(ValueError, match=message):
        normalize_recognized_markdown_v2(source)


def test_wrong_formula_content_is_not_repaired_by_presentation_normalization():
    normalized = normalize_recognized_markdown_v2(r"F01 $x_1 = 18$")

    formula = parse_labeled_formulas(normalized)[0]
    expected = parse_labeled_formulas(r"F01: $x_1 = 17$")[0]
    assert formula.signature != expected.signature


def test_horizontal_rule_is_structural_but_visible_negative_sign_is_preserved():
    normalized = normalize_recognized_markdown_v2(
        "ORDER-FIRST: AURORA-314\n---\ndrift = -3"
    )

    assert normalized == "ORDER-FIRST: AURORA-314\n\ndrift = -3"
