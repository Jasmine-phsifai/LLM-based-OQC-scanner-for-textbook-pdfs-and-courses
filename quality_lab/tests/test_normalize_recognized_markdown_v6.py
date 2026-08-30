"""Tests for the Phase 1 v6 formula-presentation normalizer."""

import pytest

from quality_lab.normalize_recognized_markdown_v6 import (
    normalize_recognized_markdown_v6,
)
from quality_lab.parse_formula_signature import parse_labeled_formulas


def test_single_ascii_symbol_text_groups_unwrap_only_inside_labeled_formulas():
    markdown = (
        r"F05: $\text{P}(A \mid B) = 0.625$" "\n"
        r"F11: $\text{E}[X_2] = 2.4$" "\n"
        r"prose \text{P} stays literal"
    )

    normalized = normalize_recognized_markdown_v6(markdown)

    assert normalized == (
        r"F05: $P(A \mid B) = 0.625$" "\n"
        r"F11: $E[X_2] = 2.4$" "\n"
        r"prose \text{P} stays literal"
    )
    assert tuple(item.label for item in parse_labeled_formulas(normalized)) == (
        "F05",
        "F11",
    )


@pytest.mark.parametrize(
    "unsafe",
    (
        r"F01: $\text{AB} + 1$",
        r"F01: $\text{} + 1$",
        r"F01: $\text{P Q} + 1$",
        r"F01: $\text{1} + 1$",
        r"F01: $\text{\alpha} + 1$",
    ),
)
def test_unsafe_text_groups_remain_visible_to_strict_parser_rejection(unsafe):
    normalized = normalize_recognized_markdown_v6(unsafe)

    assert normalized == unsafe
    with pytest.raises(ValueError, match=r"unsupported LaTeX command: \\text"):
        parse_labeled_formulas(normalized)


def test_non_formula_lines_without_math_wrappers_are_unchanged():
    markdown = "Title \\text{P}"

    assert normalize_recognized_markdown_v6(markdown) == markdown


def test_malformed_formula_label_remains_strictly_rejected():
    with pytest.raises(ValueError, match="outside the declared relation-only dialect"):
        normalize_recognized_markdown_v6(r"F5: $\text{P} + 1$")


def test_labeled_formula_without_math_wrapper_remains_strictly_rejected():
    with pytest.raises(ValueError, match="must use one complete math wrapper"):
        normalize_recognized_markdown_v6(r"F05: \text{P}")
