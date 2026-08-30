"""Parse a deliberately restricted LaTeX subset into typed formula atoms."""

from __future__ import annotations

import re
from dataclasses import dataclass

from quality_lab.normalize_content_units import normalize_formula_source


_GREEK_IDENTIFIERS = frozenset(
    {
        "alpha",
        "beta",
        "gamma",
        "delta",
        "epsilon",
        "lambda",
        "mu",
        "pi",
        "rho",
        "sigma",
        "theta",
        "phi",
        "omega",
    }
)
_COMMAND_OPERATORS = {"times": "×", "cdot": "·", "div": "÷", "mid": "|"}
_COMMAND_IDENTIFIERS = frozenset({"det"})
_COMMAND_RELATIONS = {
    "le": "≤",
    "leq": "≤",
    "ge": "≥",
    "geq": "≥",
    "ne": "≠",
    "neq": "≠",
}
_LABELED_DOLLAR_FORMULA = re.compile(
    r"^([A-Z][A-Z0-9_-]{0,31})\s*:\s*\$([^$]+)\$\s*$"
)
_LABELED_PAREN_FORMULA = re.compile(
    r"^([A-Z][A-Z0-9_-]{0,31})\s*:\s*\\\((.*?)\\\)\s*$"
)
_RESTRICTED_LABEL_PREFIX = re.compile(r"^[A-Z][A-Z0-9_-]{0,31}\s*:")


@dataclass(frozen=True, slots=True)
class FormulaAtom:
    """One structural or value-bearing atom in a restricted formula."""

    kind: str
    value: str = ""


@dataclass(frozen=True, slots=True)
class LabeledFormula:
    """A visible fixture label paired with one parsed formula signature."""

    label: str
    signature: tuple[FormulaAtom, ...]


def parse_formula_signature(latex: str) -> tuple[FormulaAtom, ...]:
    """Parse a formula or fail instead of guessing at unsupported syntax."""

    parser = _FormulaParser(normalize_formula_source(latex))
    signature = parser.parse()
    if not signature:
        raise ValueError("formula must contain at least one atom")
    _validate_formula_grammar(signature)
    return signature


def parse_labeled_formulas(markdown: str) -> tuple[LabeledFormula, ...]:
    """Extract line-oriented ``LABEL: $formula$`` declarations."""

    if type(markdown) is not str:
        raise TypeError("formula markdown must be a plain string")
    formulas: list[LabeledFormula] = []
    labels: set[str] = set()
    for line_number, line in enumerate(markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n"), 1):
        if not line.strip():
            continue
        match = _LABELED_DOLLAR_FORMULA.fullmatch(line.strip())
        if match is None:
            match = _LABELED_PAREN_FORMULA.fullmatch(line.strip())
        if match is None:
            if (
                "$" in line
                or "\\(" in line
                or "\\)" in line
                or "\\[" in line
                or "\\]" in line
                or _RESTRICTED_LABEL_PREFIX.match(line.strip()) is not None
            ):
                raise ValueError(f"malformed labeled formula on line {line_number}")
            continue
        label, latex = match.groups()
        if label in labels:
            raise ValueError(f"duplicate formula label: {label}")
        labels.add(label)
        formulas.append(LabeledFormula(label, parse_formula_signature(latex)))
    return tuple(formulas)


class _FormulaParser:
    def __init__(self, source: str) -> None:
        self.source = source
        self.index = 0

    def parse(self) -> tuple[FormulaAtom, ...]:
        atoms = self._parse_sequence(stop=None)
        if self.index != len(self.source):
            raise ValueError(f"unexpected formula input at offset {self.index}")
        return tuple(atoms)

    def _parse_sequence(self, stop: str | None) -> list[FormulaAtom]:
        atoms: list[FormulaAtom] = []
        while self.index < len(self.source):
            character = self.source[self.index]
            if stop is not None and character == stop:
                self.index += 1
                return atoms
            if character in "}])":
                raise ValueError(f"unmatched closing delimiter at offset {self.index}")
            if character.isspace():
                self.index += 1
                continue
            if character in "({[":
                closing = {"(": ")", "{": "}", "[": "]"}[character]
                self.index += 1
                nested = self._parse_sequence(closing)
                if not nested:
                    raise ValueError("empty formula group is unsupported")
                atoms.append(FormulaAtom("group_start", character))
                atoms.extend(nested)
                atoms.append(FormulaAtom("group_end", closing))
                continue
            if character == "‖":
                self.index += 1
                nested = self._parse_sequence("‖")
                if not nested:
                    raise ValueError("empty norm group is unsupported")
                atoms.append(FormulaAtom("group_start", "‖"))
                atoms.extend(nested)
                atoms.append(FormulaAtom("group_end", "‖"))
                continue
            if character in "_^":
                if not atoms or atoms[-1].kind in {
                    "operator",
                    "relation",
                    "unary_sign",
                    "group_start",
                    "separator",
                }:
                    raise ValueError(f"script marker has no base at offset {self.index}")
                marker = character
                script_kind = "subscript" if marker == "_" else "exponent"
                if script_kind in _scripts_on_current_base(atoms):
                    raise ValueError(
                        f"duplicate {script_kind} for one base at offset {self.index}"
                    )
                self.index += 1
                nested = self._parse_script_argument()
                atoms.append(FormulaAtom(f"{script_kind}_start"))
                atoms.extend(nested)
                atoms.append(FormulaAtom(f"{script_kind}_end"))
                continue
            if character == "\\":
                atoms.extend(self._parse_command())
                continue
            if character == "√":
                atoms.extend(self._parse_visible_square_root())
                continue
            if character.isascii() and character.isalpha():
                end = self.index + 1
                while end < len(self.source) and self.source[end].isascii() and self.source[end].isalpha():
                    end += 1
                atoms.append(FormulaAtom("identifier", self.source[self.index:end]))
                self.index = end
                continue
            if character.isascii() and character.isdigit():
                atoms.append(FormulaAtom("number", self._parse_number()))
                continue
            if character in {"=", "≠", "<", ">", "≤", "≥"}:
                atoms.append(FormulaAtom("relation", character))
                self.index += 1
                continue
            if character in {"+", "-", "−", "±"}:
                kind = "unary_sign" if _expects_operand(atoms) else "operator"
                value = "−" if character in {"-", "−"} else character
                atoms.append(FormulaAtom(kind, value))
                self.index += 1
                continue
            if character in {"×", "÷", "·", "*", "/", "|"}:
                atoms.append(FormulaAtom("operator", character))
                self.index += 1
                continue
            if character == "'":
                if not atoms or atoms[-1].kind in {
                    "operator",
                    "relation",
                    "unary_sign",
                    "group_start",
                    "separator",
                }:
                    raise ValueError(f"prime marker has no base at offset {self.index}")
                atoms.append(FormulaAtom("prime", character))
                self.index += 1
                continue
            if character == ",":
                atoms.append(FormulaAtom("separator", character))
                self.index += 1
                continue
            raise ValueError(
                f"unsupported formula character U+{ord(character):04X} at offset {self.index}"
            )
        if stop is not None:
            raise ValueError(f"missing closing delimiter {stop!r}")
        return atoms

    def _parse_script_argument(self) -> list[FormulaAtom]:
        while self.index < len(self.source) and self.source[self.index].isspace():
            self.index += 1
        if self.index >= len(self.source):
            raise ValueError("script marker must be followed by an argument")
        if self.source[self.index] == "{":
            self.index += 1
            atoms = self._parse_sequence("}")
            if not atoms:
                raise ValueError("script argument must not be empty")
            return atoms
        start = self.index
        if self.source[self.index] == "\\":
            atoms = self._parse_command()
        elif self.source[self.index].isascii() and self.source[self.index].isalpha():
            self.index += 1
            atoms = [FormulaAtom("identifier", self.source[start:self.index])]
        elif self.source[self.index].isascii() and self.source[self.index].isdigit():
            self.index += 1
            atoms = [FormulaAtom("number", self.source[start:self.index])]
        else:
            raise ValueError(f"unsupported script argument at offset {self.index}")
        return atoms

    def _parse_command(self) -> list[FormulaAtom]:
        command_offset = self.index
        self.index += 1
        end = self.index
        while end < len(self.source) and self.source[end].isascii() and self.source[end].isalpha():
            end += 1
        if end == self.index:
            raise ValueError(f"LaTeX command name missing at offset {command_offset}")
        command = self.source[self.index:end]
        self.index = end
        if command == "frac":
            numerator = self._parse_required_braced_argument("fraction numerator")
            denominator = self._parse_required_braced_argument("fraction denominator")
            return [
                FormulaAtom("numerator_start"),
                *numerator,
                FormulaAtom("numerator_end"),
                FormulaAtom("denominator_start"),
                *denominator,
                FormulaAtom("denominator_end"),
            ]
        if command == "sqrt":
            radicand = self._parse_required_braced_argument("square-root radicand")
            return [
                FormulaAtom("root_start"),
                *radicand,
                FormulaAtom("root_end"),
            ]
        if command in _COMMAND_OPERATORS:
            return [FormulaAtom("operator", _COMMAND_OPERATORS[command])]
        if command in _COMMAND_RELATIONS:
            return [FormulaAtom("relation", _COMMAND_RELATIONS[command])]
        if command in _GREEK_IDENTIFIERS:
            return [FormulaAtom("identifier", command)]
        if command in _COMMAND_IDENTIFIERS:
            return [FormulaAtom("identifier", command)]
        if command == "prime":
            return [FormulaAtom("prime", "'")]
        raise ValueError(f"unsupported LaTeX command: \\{command}")

    def _parse_required_braced_argument(self, description: str) -> list[FormulaAtom]:
        while self.index < len(self.source) and self.source[self.index].isspace():
            self.index += 1
        if self.index >= len(self.source) or self.source[self.index] != "{":
            raise ValueError(f"{description} must be braced")
        self.index += 1
        atoms = self._parse_sequence("}")
        if not atoms:
            raise ValueError(f"{description} must not be empty")
        return atoms

    def _parse_visible_square_root(self) -> list[FormulaAtom]:
        self.index += 1
        while self.index < len(self.source) and self.source[self.index].isspace():
            self.index += 1
        if self.index >= len(self.source):
            raise ValueError("visible square root must have a radicand")
        character = self.source[self.index]
        if character.isascii() and character.isdigit():
            radicand = [FormulaAtom("number", self._parse_number())]
        elif character.isascii() and character.isalpha():
            self.index += 1
            radicand = [FormulaAtom("identifier", character)]
        elif character in "({[":
            closing = {"(": ")", "{": "}", "[": "]"}[character]
            self.index += 1
            nested = self._parse_sequence(closing)
            if not nested:
                raise ValueError("visible square-root group must not be empty")
            radicand = [
                FormulaAtom("group_start", character),
                *nested,
                FormulaAtom("group_end", closing),
            ]
        else:
            raise ValueError("visible square-root radicand is unsupported")
        return [FormulaAtom("root_start"), *radicand, FormulaAtom("root_end")]

    def _parse_number(self) -> str:
        start = self.index
        while self.index < len(self.source) and self.source[self.index].isascii() and self.source[self.index].isdigit():
            self.index += 1
        if (
            self.index + 1 < len(self.source)
            and self.source[self.index] == "."
            and self.source[self.index + 1].isascii()
            and self.source[self.index + 1].isdigit()
        ):
            self.index += 2
            while self.index < len(self.source) and self.source[self.index].isascii() and self.source[self.index].isdigit():
                self.index += 1
        return self.source[start:self.index]


def _expects_operand(atoms: list[FormulaAtom]) -> bool:
    return not atoms or atoms[-1].kind in {
        "operator",
        "relation",
        "separator",
        "unary_sign",
        "group_start",
        "subscript_start",
        "exponent_start",
        "numerator_start",
        "denominator_start",
    }


def _scripts_on_current_base(atoms: list[FormulaAtom]) -> frozenset[str]:
    """Return trailing script kinds already attached to the current base."""

    found: set[str] = set()
    index = len(atoms) - 1
    while index >= 0 and atoms[index].kind in {"subscript_end", "exponent_end"}:
        script_kind = atoms[index].kind.removesuffix("_end")
        end_kind = f"{script_kind}_end"
        start_kind = f"{script_kind}_start"
        depth = 1
        index -= 1
        while index >= 0 and depth:
            if atoms[index].kind == end_kind:
                depth += 1
            elif atoms[index].kind == start_kind:
                depth -= 1
            index -= 1
        if depth:
            raise ValueError("unbalanced script signature")
        found.add(script_kind)
    return frozenset(found)


def _validate_formula_grammar(signature: tuple[FormulaAtom, ...]) -> None:
    final_index = _validate_expression(signature, 0, stop_kind=None)
    if final_index != len(signature):
        raise ValueError("formula grammar did not consume the full signature")


def _validate_expression(
    signature: tuple[FormulaAtom, ...], index: int, stop_kind: str | None
) -> int:
    expects_operand = True
    previous_kind: str | None = None
    saw_operand = False
    while index < len(signature):
        atom = signature[index]
        if atom.kind == stop_kind:
            if expects_operand or not saw_operand:
                raise ValueError("formula group ends without a complete operand")
            return index + 1
        if atom.kind.endswith("_end"):
            raise ValueError(f"unexpected formula structure marker: {atom.kind}")
        if atom.kind in {"identifier", "number"}:
            expects_operand = False
            saw_operand = True
            previous_kind = "operand"
            index += 1
            continue
        if atom.kind == "group_start":
            index = _validate_expression(signature, index + 1, "group_end")
            expects_operand = False
            saw_operand = True
            previous_kind = "operand"
            continue
        if atom.kind == "numerator_start":
            index = _validate_expression(signature, index + 1, "numerator_end")
            if index >= len(signature) or signature[index].kind != "denominator_start":
                raise ValueError("fraction numerator must be followed by a denominator")
            index = _validate_expression(signature, index + 1, "denominator_end")
            expects_operand = False
            saw_operand = True
            previous_kind = "operand"
            continue
        if atom.kind == "root_start":
            index = _validate_expression(signature, index + 1, "root_end")
            expects_operand = False
            saw_operand = True
            previous_kind = "operand"
            continue
        if atom.kind in {"subscript_start", "exponent_start"}:
            if expects_operand:
                raise ValueError("formula script must follow a complete base")
            stop = atom.kind.removesuffix("_start") + "_end"
            index = _validate_expression(signature, index + 1, stop)
            expects_operand = False
            previous_kind = "operand"
            continue
        if atom.kind == "unary_sign":
            previous_atom = signature[index - 1] if index else None
            follows_additive_operator = (
                previous_atom is not None
                and previous_atom.kind == "operator"
                and previous_atom.value in {"+", "-", "−", "±"}
            )
            if (
                not expects_operand
                or previous_kind == "unary_sign"
                or follows_additive_operator
            ):
                raise ValueError("unary sign is not in a supported operand position")
            previous_kind = "unary_sign"
            index += 1
            continue
        if atom.kind == "prime":
            if expects_operand:
                raise ValueError("formula prime must follow a complete base")
            previous_kind = "operand"
            index += 1
            continue
        if atom.kind in {"operator", "relation", "separator"}:
            if expects_operand:
                raise ValueError(f"{atom.kind} is missing a left operand")
            expects_operand = True
            previous_kind = atom.kind
            index += 1
            continue
        raise ValueError(f"unsupported formula signature atom: {atom.kind}")
    if stop_kind is not None:
        raise ValueError(f"missing formula structure marker: {stop_kind}")
    if expects_operand or not saw_operand:
        raise ValueError("formula ends without a complete operand")
    return index
