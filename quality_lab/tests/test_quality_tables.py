import pytest

from quality_lab.parse_markdown_tables import parse_markdown_table
from quality_lab.rational_score import RationalScore
from quality_lab.score_table_cells import (
    ExpectedMarkdownTable,
    ExpectedTableCell,
    score_table_cells,
)


def _cell(value, *, critical=False):
    return ExpectedTableCell((value,), critical=critical)


def test_numeric_table_expectation_cannot_omit_the_critical_annotation():
    with pytest.raises(ValueError, match="must be critical"):
        ExpectedTableCell(("7",))


EXPECTED_TABLE = ExpectedMarkdownTable(
    header=(_cell("Name"), _cell("Value")),
    rows=(
        (_cell("A"), _cell("-12.50", critical=True)),
        (_cell("B"), _cell("7", critical=True)),
    ),
)

PASSING_TABLE = "\n".join(
    (
        "| Name | Value |",
        "| --- | ---: |",
        "| A | -12.50 |",
        "| B | 7 |",
    )
)


def test_rectangular_gfm_table_scores_cells_at_exact_coordinates():
    parsed = parse_markdown_table(PASSING_TABLE)
    assert parsed.header == ("Name", "Value")
    assert parsed.rows == (("A", "-12.50"), ("B", "7"))
    score = score_table_cells(EXPECTED_TABLE, PASSING_TABLE)
    assert score.header_accuracy == RationalScore(2, 2)
    assert score.data_cell_accuracy == RationalScore(4, 4)
    assert score.critical_accuracy == RationalScore(2, 2)
    assert score.unexpected_coordinate_count == 0


@pytest.mark.parametrize(
    "corrupted",
    (
        PASSING_TABLE.replace("-12.50", "-12.51"),
        PASSING_TABLE.replace("-12.50", "12.50"),
        PASSING_TABLE.replace("| A | -12.50 |\n| B | 7 |", "| A | 7 |\n| B | -12.50 |"),
    ),
)
def test_digit_sign_and_coordinate_corruptions_fail_critical_cells(corrupted):
    score = score_table_cells(EXPECTED_TABLE, corrupted)
    assert score.data_cell_accuracy.numerator < score.data_cell_accuracy.denominator
    assert score.critical_accuracy.numerator < score.critical_accuracy.denominator


def test_header_corruption_is_a_separate_exact_gate():
    score = score_table_cells(EXPECTED_TABLE, PASSING_TABLE.replace("Value", "Values"))
    assert score.header_accuracy == RationalScore(1, 2)
    assert score.data_cell_accuracy == RationalScore(4, 4)


@pytest.mark.parametrize("line_break", ("<br>", "<br/>", "<br />"))
def test_exact_precommitted_html_line_breaks_are_neutral_in_cells(line_break):
    expected = ExpectedMarkdownTable(
        header=(_cell("Run 组次"), _cell("Value 数值")),
        rows=((_cell("A"), _cell("7", critical=True)),),
    )
    recognized = "\n".join(
        (
            f"| Run{line_break}组次 | Value{line_break}数值 |",
            "| --- | ---: |",
            "| A | 7 |",
        )
    )
    score = score_table_cells(expected, recognized)
    assert score.header_accuracy == RationalScore(2, 2)
    assert score.data_cell_accuracy == RationalScore(2, 2)


def test_extra_header_column_prevents_the_exact_header_gate_from_passing():
    extra_column = "\n".join(
        (
            "| Name | Value | Notes |",
            "| --- | ---: | --- |",
            "| A | -12.50 | ok |",
            "| B | 7 | ok |",
        )
    )
    score = score_table_cells(EXPECTED_TABLE, extra_column)
    assert score.header_accuracy == RationalScore(2, 3)
    assert score.unexpected_coordinate_count == 2


def test_extra_data_row_is_reported_as_unexpected_coordinates():
    score = score_table_cells(EXPECTED_TABLE, PASSING_TABLE + "\n| C | 9 |")
    assert score.unexpected_coordinate_count == 2


def test_transposed_values_are_not_matched_outside_their_coordinates():
    transposed = "\n".join(
        (
            "| Name | A | B |",
            "| --- | --- | --- |",
            "| Value | -12.50 | 7 |",
        )
    )
    score = score_table_cells(EXPECTED_TABLE, transposed)
    assert score.data_cell_accuracy.numerator < score.data_cell_accuracy.denominator
    assert score.unexpected_coordinate_count > 0


@pytest.mark.parametrize(
    "malformed,match",
    (
        ("| A | B |\n| --- | --- |\n| 1 |", "ragged table row"),
        ("| A | B |\n| nope | --- |\n| 1 | 2 |", "GFM separators"),
        ("| A | B |\n\n| --- | --- |\n| 1 | 2 |", "blank"),
        ("| A | B\\|C |\n| --- | --- |\n| 1 | 2 |", "embedded pipes"),
    ),
)
def test_malformed_or_extended_table_dialects_fail_closed(malformed, match):
    with pytest.raises(ValueError, match=match):
        parse_markdown_table(malformed)
