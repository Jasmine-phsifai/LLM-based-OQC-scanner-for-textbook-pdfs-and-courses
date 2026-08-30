"""Tests for the Phase 1 v4 diagram-connector normalizer."""

import pytest

from quality_lab.normalize_recognized_markdown_v4 import (
    normalize_recognized_markdown_v4,
)


def test_line_leading_unicode_and_latex_connectors_are_structural():
    markdown = (
        r"* $\rightarrow$ Nuclease: Cut" "\n"
        r"- $\downarrow$ +" "\n"
        r"  \rightarrow Ligase: join" "\n"
        "↓ Validation"
    )

    assert normalize_recognized_markdown_v4(markdown) == (
        "* Nuclease: Cut\n- +\nLigase: join\nValidation"
    )


def test_inline_latex_connector_remains_content_and_is_rejected():
    with pytest.raises(ValueError, match="outside the declared relation-only dialect"):
        normalize_recognized_markdown_v4(r"A $\rightarrow$ B")


def test_inline_raw_connector_is_not_reclassified_as_layout():
    assert normalize_recognized_markdown_v4(r"A \downarrow B") == r"A \downarrow B"
