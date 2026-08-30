"""Tests for the versioned Phase 1 v3 presentation normalizer."""

import pytest

from quality_lab.build_scoring_views import build_scoring_views
from quality_lab.normalize_recognized_markdown_v3 import (
    normalize_recognized_markdown_v3,
)
from quality_lab.tokenize_content_units import tokenize_content_units


def test_slanted_relation_typography_uses_the_existing_visible_relation_tokens():
    normalized = normalize_recognized_markdown_v3(
        "TARGET RECALL: ⩾ 95%\nLOWER BOUND: ⩽ 5%"
    )

    assert normalized == "TARGET RECALL: ≥ 95%\nLOWER BOUND: ≤ 5%"
    assert build_scoring_views(normalized, neutral_markdown=()).text == normalized


def test_only_line_leading_diagram_connector_is_structural():
    normalized = normalize_recognized_markdown_v3(
        "→ Nuclease: Cut\n  → Ligase: join\nA → B"
    )

    assert normalized == "Nuclease: Cut\nLigase: join\nA → B"
    with pytest.raises(ValueError, match="U\\+2192"):
        tokenize_content_units(
            build_scoring_views(normalized, neutral_markdown=()).text
        )


@pytest.mark.parametrize("wrong", ("TARGET: > 95%", "TARGET: < 95%", "TARGET: = 95%"))
def test_wrong_relation_content_is_not_repaired(wrong):
    assert normalize_recognized_markdown_v3(wrong) == wrong
