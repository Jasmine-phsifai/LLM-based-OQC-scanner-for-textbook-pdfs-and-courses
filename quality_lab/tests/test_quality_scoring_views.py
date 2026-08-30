import pytest

from quality_lab.build_scoring_views import build_scoring_views
from quality_lab.score_formula_signatures import (
    ExpectedFormula,
    score_formula_signatures,
)


NEUTRAL_MARKDOWN = (
    "headings",
    "unordered_list_markers",
    "ordered_list_markers",
    "emphasis",
    "formula_delimiters",
    "table_delimiters",
)


def test_views_remove_only_declared_scaffolding_and_isolate_typed_regions():
    markdown = "\n".join(
        (
            "# **Board title**",
            "- TARGET: 95%",
            "1. 中文、值",
            r"- **F01**: \(x_1 = -3\)",
            "| Run | Value |",
            "| --- | ---: |",
            "| A-01 | 12.57 |",
            "ORDER-LAST: ZENITH-926",
        )
    )

    views = build_scoring_views(markdown, neutral_markdown=NEUTRAL_MARKDOWN)

    assert views.text == "\n".join(
        ("Board title", "TARGET: 95%", "中文、值", "ORDER-LAST: ZENITH-926")
    )
    assert views.anchors == views.text
    assert views.formulas == "F01: $x_1 = -3$"
    assert views.table == "\n".join(
        ("| Run | Value |", "| --- | ---: |", "| A-01 | 12.57 |")
    )


@pytest.mark.parametrize(
    "source",
    (
        r"F01: $x_1=2$",
        r"- **F01**: \(x_1=2\)",
        r"1. __F01__: $$x_1=2$$",
        r"F01: \[x_1=2\]",
    ),
)
def test_fixed_formula_wrappers_canonicalize_before_formula_scoring(source):
    views = build_scoring_views(source, neutral_markdown=NEUTRAL_MARKDOWN)
    assert views.formulas == "F01: $x_1=2$"
    assert views.text == ""


def test_list_prefix_removal_preserves_visible_signs_and_relations():
    views = build_scoring_views(
        "- drift = -3\n2. gain ≥ 1.25\n+ foreign gene",
        neutral_markdown=NEUTRAL_MARKDOWN,
    )
    assert views.text == "drift = -3\ngain ≥ 1.25\n+ foreign gene"


@pytest.mark.parametrize(
    "source",
    (
        "F01: x=1",
        "F01: $x=1",
        "price is $5",
    ),
)
def test_malformed_or_unlabeled_formula_syntax_fails_closed(source):
    with pytest.raises(ValueError, match="malformed labeled formula"):
        build_scoring_views(source, neutral_markdown=NEUTRAL_MARKDOWN)


def test_more_than_one_table_fails_instead_of_selecting_a_favorable_block():
    markdown = "\n\n".join(
        (
            "| A |\n| --- |\n| 1 |",
            "| B |\n| --- |\n| 2 |",
        )
    )
    with pytest.raises(ValueError, match="more than one table"):
        build_scoring_views(markdown, neutral_markdown=NEUTRAL_MARKDOWN)


def test_stray_or_malformed_table_rows_cannot_escape_the_table_channel():
    valid_then_stray = "\n".join(
        ("| A |", "| --- |", "| 1 |", "caption", "| invented 99 |")
    )
    with pytest.raises(ValueError, match="outside its table"):
        build_scoring_views(valid_then_stray, neutral_markdown=NEUTRAL_MARKDOWN)
    with pytest.raises(ValueError, match="malformed table syntax"):
        build_scoring_views("| no separator | 99 |", neutral_markdown=NEUTRAL_MARKDOWN)


def test_formula_literal_bar_is_isolated_before_stray_table_pipe_detection():
    views = build_scoring_views(
        r"F05: $P(A | B) = 0.625$",
        neutral_markdown=NEUTRAL_MARKDOWN,
    )
    assert views.formulas == r"F05: $P(A | B) = 0.625$"
    assert views.table is None


def test_two_column_formula_table_is_layout_not_an_unexpected_data_table():
    markdown = "\n".join(
        (
            "| ID | Formula |",
            "| --- | --- |",
            r"| F01 | $a_1 + a_2 = 17$ |",
            r"| F02 | \[x_1 - 3x_2 \le -4\] |",
            "ORDER-LAST: ZENITH-926",
        )
    )
    views = build_scoring_views(markdown, neutral_markdown=NEUTRAL_MARKDOWN)
    assert views.formulas == "\n".join(
        (r"F01: $a_1 + a_2 = 17$", r"F02: $x_1 - 3x_2 \le -4$")
    )
    assert views.table is None
    assert views.text == "ORDER-LAST: ZENITH-926"


def test_formula_table_routes_extra_columns_to_undeclared_table_channel_and_rejects_headers():
    extra_column = "\n".join(
        (
            "| ID | Formula | Notes |",
            "| --- | --- | --- |",
            r"| F01 | $x=1$ | invented |",
        )
    )
    extra_views = build_scoring_views(
        extra_column,
        neutral_markdown=NEUTRAL_MARKDOWN,
    )
    assert extra_views.formulas == ""
    assert extra_views.table == extra_column

    unsupported_header = "\n".join(
        ("| Item | Math |", "| --- | --- |", r"| F01 | $x=1$ |")
    )
    with pytest.raises(ValueError, match="unsupported header"):
        build_scoring_views(unsupported_header, neutral_markdown=NEUTRAL_MARKDOWN)


def test_neutral_markdown_rules_are_closed_and_unique():
    with pytest.raises(ValueError, match="unsupported neutral Markdown rule"):
        build_scoring_views("text", neutral_markdown=("html",))
    with pytest.raises(ValueError, match="must not contain duplicates"):
        build_scoring_views("text", neutral_markdown=("headings", "headings"))


@pytest.mark.parametrize(
    ("source", "unchanged"),
    (
        (r"F01: $x**2$", r"F01: $x**2$"),
        (r"F01: $x__2$", r"F01: $x__2$"),
        (r"F01: $$x**2$$", r"F01: $x**2$"),
        (r"F01: \(x__2\)", r"F01: $x__2$"),
        (r"F01: \[x**2\]", r"F01: $x**2$"),
        (r"F01: $**3**x_2$", r"F01: $**3**x_2$"),
        (r"F01: $x__1__$", r"F01: $x__1__$"),
    ),
)
def test_emphasis_markers_inside_math_are_preserved_and_fail_formula_parsing(
    source,
    unchanged,
):
    views = build_scoring_views(source, neutral_markdown=NEUTRAL_MARKDOWN)
    assert views.formulas == unchanged
    with pytest.raises(ValueError):
        score_formula_signatures(
            (ExpectedFormula("F01", ("x2",)),),
            views.formulas,
        )


def test_emphasis_cleanup_still_supports_labels_and_rejects_unbalanced_prose():
    views = build_scoring_views(
        r"**F01**: \(x_1=2\)",
        neutral_markdown=NEUTRAL_MARKDOWN,
    )
    assert views.formulas == r"F01: $x_1=2$"
    with pytest.raises(ValueError, match="ambiguous emphasis"):
        build_scoring_views(
            "**unfinished",
            neutral_markdown=NEUTRAL_MARKDOWN,
        )
