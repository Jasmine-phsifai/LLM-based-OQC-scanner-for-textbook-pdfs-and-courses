"""Tests for the Phase 1 v7 formula-presentation normalizer."""

import pytest

from quality_lab.normalize_recognized_markdown_v7 import (
    normalize_recognized_markdown_v7,
)
from quality_lab.parse_formula_signature import parse_labeled_formulas


def test_single_ascii_mathrm_groups_unwrap_only_inside_labeled_formulas():
    markdown = (
        r"F05: $\mathrm{P}(\mathrm{A} \mid \mathrm{B}) = 0.625$" "\n"
        r"F06: $\det(\mathrm{M}) = 14$" "\n"
        r"F11: $\mathrm{E}[X_2] = 2.4$" "\n"
        r"prose \mathrm{P} stays literal"
    )

    normalized = normalize_recognized_markdown_v7(markdown)

    assert normalized == (
        r"F05: $P(A \mid B) = 0.625$" "\n"
        r"F06: $\det(M) = 14$" "\n"
        r"F11: $E[X_2] = 2.4$" "\n"
        r"prose \mathrm{P} stays literal"
    )
    formula_only = "\n".join(normalized.splitlines()[:3])
    assert tuple(item.label for item in parse_labeled_formulas(formula_only)) == (
        "F05",
        "F06",
        "F11",
    )


@pytest.mark.parametrize(
    "unsafe",
    (
        r"F01: $\mathrm{AB} + 1$",
        r"F01: $\mathrm{} + 1$",
        r"F01: $\mathrm{P Q} + 1$",
        r"F01: $\mathrm{1} + 1$",
        r"F01: $\mathrm{\alpha} + 1$",
    ),
)
def test_unsafe_mathrm_groups_remain_visible_to_strict_parser_rejection(unsafe):
    normalized = normalize_recognized_markdown_v7(unsafe)

    assert normalized == unsafe
    with pytest.raises(ValueError, match=r"unsupported LaTeX command: \\mathrm"):
        parse_labeled_formulas(normalized)


def test_v7_retains_v6_single_letter_text_normalization():
    assert normalize_recognized_markdown_v7(r"F05: $\text{P}(A)=1$") == (
        r"F05: $P(A)=1$"
    )


def test_non_formula_mathrm_is_unchanged():
    markdown = r"Title \mathrm{P}"

    assert normalize_recognized_markdown_v7(markdown) == markdown
