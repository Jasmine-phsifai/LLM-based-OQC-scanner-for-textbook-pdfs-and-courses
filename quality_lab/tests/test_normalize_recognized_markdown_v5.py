"""Tests for the Phase 1 v5 ASCII diagram-connector normalizer."""

from quality_lab.normalize_recognized_markdown_v5 import (
    normalize_recognized_markdown_v5,
)


def test_only_line_leading_ascii_connectors_are_structural():
    markdown = (
        "-> Nuclease: Cut\n"
        "  -> Ligase: join\n"
        "* -> Selection\n"
        "1. -> Screening\n"
        "A -> B\n"
        "--> comment"
    )

    assert normalize_recognized_markdown_v5(markdown) == (
        "Nuclease: Cut\n"
        "Ligase: join\n"
        "* Selection\n"
        "1. Screening\n"
        "A -> B\n"
        "--> comment"
    )


def test_ascii_connector_without_payload_is_structural_but_inline_relation_is_not():
    assert normalize_recognized_markdown_v5("->\nA -> B") == "\nA -> B"
