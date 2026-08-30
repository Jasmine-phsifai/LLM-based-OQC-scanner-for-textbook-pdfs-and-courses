"""Score labeled formulas by exact signature and ordered atom matching."""

from __future__ import annotations

import re
from dataclasses import dataclass

from quality_lab.parse_formula_signature import (
    FormulaAtom,
    parse_formula_signature,
    parse_labeled_formulas,
)
from quality_lab.rational_score import PERFECT_SCORE, ZERO_SCORE, RationalScore


_DEFAULT_CRITICAL_KINDS = frozenset(
    {
        "number",
        "operator",
        "relation",
        "unary_sign",
        "subscript_start",
        "subscript_end",
        "exponent_start",
        "exponent_end",
        "group_start",
        "group_end",
        "numerator_start",
        "numerator_end",
        "denominator_start",
        "denominator_end",
        "root_start",
        "root_end",
        "prime",
        "separator",
    }
)
_FORMULA_LABEL = re.compile(r"^[A-Z][A-Z0-9_-]{0,31}$")


@dataclass(frozen=True, slots=True)
class ExpectedFormula:
    """One uniquely labeled formula and its precommitted equivalent forms."""

    label: str
    accepted_latex: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.label) is not str or _FORMULA_LABEL.fullmatch(self.label) is None:
            raise ValueError("formula label must match the restricted uppercase label syntax")
        if type(self.accepted_latex) is not tuple or not self.accepted_latex:
            raise ValueError("accepted_latex must be a non-empty tuple")
        if any(type(value) is not str or not value.strip() for value in self.accepted_latex):
            raise ValueError("accepted_latex values must be non-empty plain strings")


@dataclass(frozen=True, slots=True)
class FormulaScore:
    """Exact formula metrics and hard insertion evidence."""

    signature_accuracy: RationalScore
    atom_precision: RationalScore
    critical_accuracy: RationalScore
    missing_labels: tuple[str, ...]
    unexpected_labels: tuple[str, ...]
    missing_atom_count: int
    unexpected_atom_count: int


def score_formula_signatures(
    expected: tuple[ExpectedFormula, ...], recognized_markdown: str
) -> FormulaScore:
    """Score labeled formulas without algebraic or semantic equivalence guesses."""

    expected_signatures = _parse_and_validate_expected(expected)
    recognized = parse_labeled_formulas(recognized_markdown)
    recognized_by_label = {formula.label: formula.signature for formula in recognized}
    expected_labels = {formula.label for formula in expected}
    exact_count = 0
    matched_atom_count = 0
    recognized_atom_count = sum(len(formula.signature) for formula in recognized)
    expected_atom_count = 0
    critical_count = 0
    matched_critical_count = 0
    missing_labels: list[str] = []

    for formula, options in zip(expected, expected_signatures, strict=True):
        actual = recognized_by_label.get(formula.label)
        if actual is None:
            missing_labels.append(formula.label)
            selected = options[0]
            expected_atom_count += len(selected)
            critical_count += _critical_count(selected)
            continue
        candidates = [
            (
                int(actual == option),
                _lcs_length(option, actual),
                _critical_matches_at_same_indexes(option, actual),
                -index,
                option,
            )
            for index, option in enumerate(options)
        ]
        exact, matched, critical_matched, _, selected = max(candidates, key=lambda item: item[:4])
        exact_count += exact
        matched_atom_count += matched
        matched_critical_count += critical_matched
        expected_atom_count += len(selected)
        critical_count += _critical_count(selected)

    unexpected_labels = tuple(
        formula.label for formula in recognized if formula.label not in expected_labels
    )
    return FormulaScore(
        signature_accuracy=(
            RationalScore(exact_count, len(expected)) if expected else PERFECT_SCORE
        ),
        atom_precision=(
            RationalScore(matched_atom_count, recognized_atom_count)
            if recognized_atom_count
            else ZERO_SCORE
        ),
        critical_accuracy=(
            RationalScore(matched_critical_count, critical_count)
            if critical_count
            else PERFECT_SCORE
        ),
        missing_labels=tuple(missing_labels),
        unexpected_labels=unexpected_labels,
        missing_atom_count=expected_atom_count - matched_atom_count,
        unexpected_atom_count=recognized_atom_count - matched_atom_count,
    )


def _parse_and_validate_expected(
    expected: tuple[ExpectedFormula, ...],
) -> tuple[tuple[tuple[FormulaAtom, ...], ...], ...]:
    if type(expected) is not tuple:
        raise TypeError("expected formulas must be a tuple")
    labels: set[str] = set()
    parsed: list[tuple[tuple[FormulaAtom, ...], ...]] = []
    for formula in expected:
        if not isinstance(formula, ExpectedFormula):
            raise TypeError("expected tuple contains a non-ExpectedFormula value")
        if formula.label in labels:
            raise ValueError(f"duplicate expected formula label: {formula.label}")
        labels.add(formula.label)
        options = tuple(parse_formula_signature(latex) for latex in formula.accepted_latex)
        if len(set(options)) != len(options):
            raise ValueError(f"duplicate accepted formula signature for {formula.label}")
        critical_projections = {
            tuple(atom for atom in option if atom.kind in _DEFAULT_CRITICAL_KINDS)
            for option in options
        }
        if len(critical_projections) != 1:
            raise ValueError(
                f"accepted signatures for {formula.label} disagree on critical atoms"
            )
        parsed.append(options)
    return tuple(parsed)


def _lcs_length(expected: tuple[FormulaAtom, ...], actual: tuple[FormulaAtom, ...]) -> int:
    previous = [0] * (len(actual) + 1)
    for expected_atom in expected:
        current = [0]
        for index, actual_atom in enumerate(actual, 1):
            if expected_atom == actual_atom:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(previous[index], current[-1]))
        previous = current
    return previous[-1]


def _critical_count(signature: tuple[FormulaAtom, ...]) -> int:
    return sum(atom.kind in _DEFAULT_CRITICAL_KINDS for atom in signature)


def _critical_matches_at_same_indexes(
    expected: tuple[FormulaAtom, ...], actual: tuple[FormulaAtom, ...]
) -> int:
    return sum(
        atom.kind in _DEFAULT_CRITICAL_KINDS
        and index < len(actual)
        and actual[index] == atom
        for index, atom in enumerate(expected)
    )
