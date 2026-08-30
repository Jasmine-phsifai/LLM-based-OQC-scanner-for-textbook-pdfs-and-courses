import pytest

from quality_lab.parse_formula_signature import (
    FormulaAtom,
    parse_formula_signature,
    parse_labeled_formulas,
)
from quality_lab.rational_score import RationalScore
from quality_lab.score_formula_signatures import (
    ExpectedFormula,
    score_formula_signatures,
)


EXPECTED_FORMULAS = (
    ExpectedFormula("F01", (r"x_1=-3",)),
    ExpectedFormula("F02", (r"y^2\leq 10",)),
    ExpectedFormula("F03", (r"\frac{a}{b}=2",)),
)

PASSING_FORMULAS = "\n".join(
    (
        r"F01: $x_1=-3$",
        r"F02: $y^2\leq 10$",
        r"F03: $\frac{a}{b}=2$",
    )
)


def test_unicode_scripts_and_latex_scripts_produce_the_same_typed_structure():
    assert parse_formula_signature("x₂=-3") == parse_formula_signature(r"x_2=-3")
    assert parse_formula_signature("y²") == (
        FormulaAtom("identifier", "y"),
        FormulaAtom("exponent_start"),
        FormulaAtom("number", "2"),
        FormulaAtom("exponent_end"),
    )


def test_labeled_formula_scorer_accepts_only_exact_structures():
    score = score_formula_signatures(EXPECTED_FORMULAS, PASSING_FORMULAS)
    assert score.signature_accuracy == RationalScore(3, 3)
    assert score.atom_precision.numerator == score.atom_precision.denominator
    assert score.critical_accuracy.numerator == score.critical_accuracy.denominator
    assert score.missing_labels == ()
    assert score.unexpected_labels == ()
    assert score.missing_atom_count == 0
    assert score.unexpected_atom_count == 0


@pytest.mark.parametrize(
    "before,after",
    (
        (r"x_1=-3", r"x_1=-4"),
        (r"x_1=-3", r"x_1=+3"),
        (r"x_1=-3", r"x_1+3"),
        (r"x_1=-3", r"x_2=-3"),
        (r"y^2\leq 10", r"y^3\leq 10"),
        (r"y^2\leq 10", r"y^2=10"),
        (r"y^2\leq 10", r"y^2+1\leq 10"),
        (r"\frac{a}{b}=2", r"a/b=2"),
    ),
)
def test_digit_sign_subscript_exponent_relation_insertion_and_grouping_corruptions_fail(
    before, after
):
    corrupted = PASSING_FORMULAS.replace(before, after)
    score = score_formula_signatures(EXPECTED_FORMULAS, corrupted)
    assert score.signature_accuracy.numerator == 2
    assert score.missing_atom_count or score.unexpected_atom_count or (
        score.critical_accuracy.numerator < score.critical_accuracy.denominator
    )


def test_unknown_formula_label_is_an_insertion_and_lowers_atom_precision():
    score = score_formula_signatures(
        EXPECTED_FORMULAS, PASSING_FORMULAS + "\n" + r"F99: $z=100$"
    )
    assert score.unexpected_labels == ("F99",)
    assert score.unexpected_atom_count == 3
    assert score.atom_precision.numerator < score.atom_precision.denominator


def test_binary_operator_substitution_fails_the_perfect_critical_channel():
    expected = (ExpectedFormula("F01", ("x+y=2",)),)
    score = score_formula_signatures(expected, "F01: $x-y=2$")
    assert score.critical_accuracy.numerator < score.critical_accuracy.denominator


def test_missing_formula_label_cannot_be_inferred_from_formula_order():
    score = score_formula_signatures(
        EXPECTED_FORMULAS, PASSING_FORMULAS.replace(r"F02: $y^2\leq 10$" + "\n", "")
    )
    assert score.missing_labels == ("F02",)
    assert score.signature_accuracy == RationalScore(2, 3)


@pytest.mark.parametrize(
    "source,match",
    (
        (r"F01: $\sin{x}$", "unsupported LaTeX command"),
        ("F01: $x=1", "malformed labeled formula"),
        ("F99: z=100", "malformed labeled formula"),
        (r"F99: \[z=100\]", "malformed labeled formula"),
        ("F01: $x=1$\nF01: $x=1$", "duplicate formula label"),
    ),
)
def test_malformed_unsupported_or_duplicate_formulas_fail_closed(source, match):
    with pytest.raises(ValueError, match=match):
        parse_labeled_formulas(source)


def test_structurally_duplicate_accepted_signatures_are_rejected_as_ambiguous():
    expected = (ExpectedFormula("F01", (r"x^2", "x²")),)
    with pytest.raises(ValueError, match="duplicate accepted formula signature"):
        score_formula_signatures(expected, r"F01: $x^2$")


def test_duplicate_script_for_one_base_is_rejected_but_subscript_then_exponent_is_valid():
    with pytest.raises(ValueError, match="duplicate subscript"):
        parse_formula_signature(r"x_1_2")
    assert parse_formula_signature(r"x_1^2")


def test_expected_formula_label_must_use_the_same_restricted_visible_syntax():
    with pytest.raises(ValueError, match="uppercase label syntax"):
        ExpectedFormula("formula one", ("x=1",))


@pytest.mark.parametrize("malformed", ("x=", "=x", "x++y", "x,,y", "x,_1"))
def test_incomplete_or_consecutive_formula_grammar_fails_closed(malformed):
    with pytest.raises(ValueError):
        parse_formula_signature(malformed)


@pytest.mark.parametrize("supported", (r"(x,-1)", r"x\times -1", "x/-2"))
def test_signed_operands_after_separators_and_multiplicative_operators_are_supported(
    supported,
):
    assert parse_formula_signature(supported)


@pytest.mark.parametrize(
    "supported",
    (
        r"P(A \mid B) = 0.625",
        r"\det(M) = 3 \times 8 - 2 \times 5 = 14",
        r"f'(x) = 6x - 5",
        r"\lVert u \rVert_{2} = \sqrt{25} = 5",
    ),
)
def test_fixture_formula_dialect_supports_only_precommitted_visible_constructs(
    supported,
):
    assert parse_formula_signature(supported)


def test_visible_bar_and_common_latex_bar_forms_share_precommitted_signatures():
    assert parse_formula_signature(r"P(A \mid B)") == parse_formula_signature(
        "P(A | B)"
    )
    assert parse_formula_signature(r"\lVert u \rVert_2") == parse_formula_signature(
        r"\|u\|_2"
    )


def test_prime_and_square_root_structure_are_critical():
    expected = (ExpectedFormula("F09", (r"f'(x)=\sqrt{25}",)),)
    missing_prime = score_formula_signatures(expected, r"F09: $f(x)=\sqrt{25}$")
    missing_root = score_formula_signatures(expected, r"F09: $f'(x)=25$")
    assert missing_prime.critical_accuracy.numerator < missing_prime.critical_accuracy.denominator
    assert missing_root.critical_accuracy.numerator < missing_root.critical_accuracy.denominator


def test_visible_unicode_prime_and_latex_ascii_prime_share_one_critical_atom():
    assert parse_formula_signature("f′(x) = 6x − 5") == parse_formula_signature(
        "f'(x) = 6x − 5"
    )


def test_visible_square_root_and_braced_latex_root_share_one_critical_structure():
    assert parse_formula_signature("‖u‖₂ = √25 = 5") == parse_formula_signature(
        r"\lVert u \rVert_{2} = \sqrt{25} = 5"
    )


def test_latex_minus_matches_visible_math_minus_only_in_formula_channel():
    assert parse_formula_signature("x = −4") == parse_formula_signature("x = -4")


@pytest.mark.parametrize(
    "alternative",
    (r"f^{\prime}(x)", r"f^\prime(x)", r"f\prime(x)"),
)
def test_common_latex_prime_forms_share_the_visible_prime_signature(alternative):
    assert parse_formula_signature(alternative) == parse_formula_signature("f'(x)")


def test_latex_sizing_commands_do_not_change_group_or_norm_structure():
    assert parse_formula_signature(r"\left(x+1\right)") == parse_formula_signature(
        "(x+1)"
    )
    assert parse_formula_signature(
        r"\left\lVert u \right\rVert_2"
    ) == parse_formula_signature(r"\lVert u \rVert_2")


@pytest.mark.parametrize(
    "malformed",
    (
        r"\lVertu \rVert_2=5",
        r"\lVert u \rVertu_2=5",
        r"\left\lVertu\right\rVert_2=5",
    ),
)
def test_norm_command_prefixes_cannot_spoof_the_expected_formula(malformed):
    expected = (ExpectedFormula("F09", (r"\lVert u \rVert_2=5",)),)
    with pytest.raises(ValueError):
        score_formula_signatures(expected, f"F09: ${malformed}$")
