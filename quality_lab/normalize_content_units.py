"""Normalize visible leaves while preserving mathematical script structure."""

from __future__ import annotations

import re
import unicodedata


NORMALIZATION_VERSION = "content-units.v1"

_SUPERSCRIPT_VALUES = dict(
    zip(
        "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ",
        "0123456789+-=()ni",
        strict=True,
    )
)
_SUBSCRIPT_VALUES = dict(
    zip(
        "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ",
        "0123456789+-=()aehijklmnoprstuvx",
        strict=True,
    )
)
_COLLAPSED_WHITESPACE = re.compile(r"\s+")
_SIZING_DELIMITER_PAIRS = {
    "(": ")",
    "[": "]",
    r"\lVert": r"\rVert",
    r"\|": r"\|",
}


def normalize_visible_text(value: str, *, case_sensitive: bool = True) -> str:
    """Normalize a non-formula leaf using the frozen Phase 1 rules."""

    _require_plain_string(value)
    normalized_newlines = value.replace("\r\n", "\n").replace("\r", "\n")
    normalized = unicodedata.normalize("NFKC", normalized_newlines)
    normalized = _COLLAPSED_WHITESPACE.sub(" ", normalized).strip()
    return normalized if case_sensitive else normalized.casefold()


def normalize_formula_source(value: str) -> str:
    """Convert Unicode script glyphs to structural LaTeX before NFKC."""

    _require_plain_string(value)
    normalized_newlines = value.replace("\r\n", "\n").replace("\r", "\n")
    protected: list[str] = []
    index = 0
    while index < len(normalized_newlines):
        character = normalized_newlines[index]
        script_values: dict[str, str] | None = None
        marker = ""
        if character in _SUPERSCRIPT_VALUES:
            script_values = _SUPERSCRIPT_VALUES
            marker = "^"
        elif character in _SUBSCRIPT_VALUES:
            script_values = _SUBSCRIPT_VALUES
            marker = "_"

        if script_values is None:
            protected.append(character)
            index += 1
            continue

        run: list[str] = []
        while index < len(normalized_newlines):
            script_character = normalized_newlines[index]
            if script_character not in script_values:
                break
            run.append(script_values[script_character])
            index += 1
        protected.extend((marker, "{", "".join(run), "}"))

    normalized = unicodedata.normalize("NFKC", "".join(protected)).replace("′", "'")
    normalized = re.sub(r"\^\s*\{\s*\\prime\s*\}", "'", normalized)
    normalized = re.sub(r"\^\s*\\prime\b", "'", normalized)
    normalized = _remove_paired_latex_sizing_commands(normalized)
    normalized = _replace_exact_latex_command(normalized, "lVert", "‖")
    normalized = _replace_exact_latex_command(normalized, "rVert", "‖")
    normalized = normalized.replace(r"\|", "‖")
    return _COLLAPSED_WHITESPACE.sub(" ", normalized).strip()


def _require_plain_string(value: object) -> None:
    if type(value) is not str:
        raise TypeError("content must be a plain string")


def _remove_paired_latex_sizing_commands(value: str) -> str:
    """Remove only paired sizing commands attached to approved delimiters."""

    result: list[str] = []
    expected_closings: list[str] = []
    index = 0
    opening_tokens = tuple(sorted(_SIZING_DELIMITER_PAIRS, key=len, reverse=True))
    closing_tokens = tuple(
        sorted(set(_SIZING_DELIMITER_PAIRS.values()), key=len, reverse=True)
    )
    while index < len(value):
        if _starts_exact_latex_command(value, index, "left"):
            delimiter_index = index + len(r"\left")
            opening = _matching_token(value, delimiter_index, opening_tokens)
            if opening is None:
                raise ValueError(
                    "\\left must be immediately followed by an approved opening delimiter"
                )
            expected_closings.append(_SIZING_DELIMITER_PAIRS[opening])
            result.append(opening)
            index = delimiter_index + len(opening)
            continue
        if _starts_exact_latex_command(value, index, "right"):
            delimiter_index = index + len(r"\right")
            closing = _matching_token(value, delimiter_index, closing_tokens)
            if closing is None:
                raise ValueError(
                    "\\right must be immediately followed by an approved closing delimiter"
                )
            if not expected_closings:
                raise ValueError("\\right has no matching \\left sizing command")
            expected = expected_closings.pop()
            if closing != expected:
                raise ValueError("\\left and \\right sizing delimiters do not match")
            result.append(closing)
            index = delimiter_index + len(closing)
            continue
        result.append(value[index])
        index += 1

    if expected_closings:
        raise ValueError("\\left sizing command has no matching \\right")
    return "".join(result)


def _starts_exact_latex_command(value: str, index: int, command: str) -> bool:
    spelling = f"\\{command}"
    if not value.startswith(spelling, index):
        return False
    following_index = index + len(spelling)
    return following_index >= len(value) or not value[following_index].isalpha()


def _replace_exact_latex_command(
    value: str,
    command: str,
    replacement: str,
) -> str:
    result: list[str] = []
    index = 0
    spelling = f"\\{command}"
    while index < len(value):
        if _starts_exact_latex_command(value, index, command):
            result.append(replacement)
            index += len(spelling)
            continue
        result.append(value[index])
        index += 1
    return "".join(result)


def _matching_token(
    value: str,
    index: int,
    candidates: tuple[str, ...],
) -> str | None:
    return next(
        (
            candidate
            for candidate in candidates
            if value.startswith(candidate, index)
            and (
                not _is_latex_control_word(candidate)
                or _starts_exact_latex_command(value, index, candidate[1:])
            )
        ),
        None,
    )


def _is_latex_control_word(value: str) -> bool:
    return bool(value.startswith("\\") and value[1:] and value[1:].isalpha())
