import unicodedata

import pytest

from quality_lab.normalize_content_units import (
    NORMALIZATION_VERSION,
    normalize_formula_source,
    normalize_visible_text,
)
from quality_lab.parse_formula_signature import parse_formula_signature
from quality_lab.tokenize_content_units import (
    TOKENIZER_VERSION,
    tokenize_content_units,
)


def test_formula_scripts_are_protected_before_nfkc_flattens_them():
    assert unicodedata.normalize("NFKC", "x²+y₂₃") == "x2+y23"
    assert normalize_formula_source("x²+y₂₃") == "x^{2}+y_{23}"


def test_visible_normalization_is_versioned_and_preserves_minus_identity():
    assert NORMALIZATION_VERSION == "content-units.v1"
    assert TOKENIZER_VERSION == "content-units.v1"
    assert normalize_visible_text("  Ａ\r\n  −  -  ") == "A − -"
    assert normalize_visible_text("Straße", case_sensitive=False) == "strasse"


def test_text_lexer_emits_words_individual_han_decimals_signs_and_relations():
    tokens = tokenize_content_units("Optimization、优化 ４７.２５ − 3 ≤ 95%")
    assert tuple((token.kind, token.value) for token in tokens) == (
        ("word", "Optimization"),
        ("han", "优"),
        ("han", "化"),
        ("number", "47.25"),
        ("sign", "−"),
        ("number", "3"),
        ("relation", "≤"),
        ("number", "95"),
        ("unit", "%"),
    )


def test_text_lexer_does_not_silently_discard_unknown_scripts():
    with pytest.raises(ValueError, match="unsupported visible character"):
        tokenize_content_units("Latin Ж")


def test_normalizers_reject_string_subclasses_before_calling_overrides():
    class HostileText(str):
        def replace(self, *args, **kwargs):
            raise AssertionError("hostile string override was called")

    with pytest.raises(TypeError, match="plain string"):
        normalize_visible_text(HostileText("secret"))
    with pytest.raises(TypeError, match="plain string"):
        normalize_formula_source(HostileText("x²"))


def test_paired_sizing_commands_are_removed_only_before_approved_delimiters():
    assert normalize_formula_source(r"\left(x+1\right)") == "(x+1)"
    assert normalize_formula_source(
        r"\left\lVert u \right\rVert_2"
    ) == "‖ u ‖_2"
    assert normalize_formula_source(
        r"\left(\left[x\right]\right)"
    ) == "([x])"


@pytest.mark.parametrize(
    "malformed",
    (
        r"\leftx",
        r"\rightx",
        r"\left x",
        r"\right x",
        r"\left(x)",
        r"(x\right)",
        r"\left[x\right)",
    ),
)
def test_malformed_spaced_unpaired_or_mismatched_sizing_commands_fail(malformed):
    with pytest.raises(ValueError):
        parse_formula_signature(malformed)


def test_norm_control_words_keep_valid_tex_boundaries():
    assert normalize_formula_source(r"\lVert u \rVert_2") == "‖ u ‖_2"
    assert normalize_formula_source(r"\lVert{u}\rVert_2") == "‖{u}‖_2"
    assert normalize_formula_source(r"\lVert1\rVert") == "‖1‖"


@pytest.mark.parametrize(
    "malformed",
    (
        r"\lVertu \rVert_2",
        r"\lVert u \rVertu_2",
        r"\lVertu\rVertu",
        r"\left\lVertu\right\rVert_2",
        r"\left\lVert u\right\rVertu_2",
    ),
)
def test_norm_command_prefixes_are_not_split_into_valid_commands(malformed):
    with pytest.raises(ValueError):
        parse_formula_signature(malformed)
