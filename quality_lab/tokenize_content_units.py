"""Tokenize visible text with the frozen Phase 1 content-unit lexer."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from quality_lab.normalize_content_units import normalize_visible_text


TOKENIZER_VERSION = "content-units.v1"

_SIGNS = frozenset({"+", "-", "−", "±"})
_RELATIONS = frozenset({"=", "≠", "<", ">", "≤", "≥"})
_OPERATORS = frozenset({"×", "÷", "*", "/"})
_UNITS = frozenset({"%", "‰", "°"})
_IGNORED_PUNCTUATION = frozenset(
    ".,:;!?，。；：！？、'\"“”‘’()[]{}#_~`|"
)


@dataclass(frozen=True, slots=True)
class ContentToken:
    """One scored visible-content occurrence."""

    kind: str
    value: str
    start: int
    end: int


def tokenize_content_units(value: str) -> tuple[ContentToken, ...]:
    """Return significant units, rejecting characters outside the fixed dialect."""

    normalized = normalize_visible_text(value)
    tokens: list[ContentToken] = []
    index = 0
    while index < len(normalized):
        character = normalized[index]
        if character.isspace():
            index += 1
            continue
        if _is_han(character):
            tokens.append(ContentToken("han", character, index, index + 1))
            index += 1
            continue
        if _is_latin_letter(character):
            end = index + 1
            while end < len(normalized) and (
                _is_latin_letter(normalized[end])
                or unicodedata.category(normalized[end]).startswith("M")
            ):
                end += 1
            tokens.append(ContentToken("word", normalized[index:end], index, end))
            index = end
            continue
        if character.isascii() and character.isdigit():
            end = index + 1
            while end < len(normalized) and normalized[end].isascii() and normalized[end].isdigit():
                end += 1
            if (
                end + 1 < len(normalized)
                and normalized[end] == "."
                and normalized[end + 1].isascii()
                and normalized[end + 1].isdigit()
            ):
                end += 2
                while end < len(normalized) and normalized[end].isascii() and normalized[end].isdigit():
                    end += 1
            tokens.append(ContentToken("number", normalized[index:end], index, end))
            index = end
            continue
        if character in _SIGNS:
            tokens.append(ContentToken("sign", character, index, index + 1))
            index += 1
            continue
        if character in _RELATIONS:
            tokens.append(ContentToken("relation", character, index, index + 1))
            index += 1
            continue
        if character in _OPERATORS:
            tokens.append(ContentToken("operator", character, index, index + 1))
            index += 1
            continue
        if character in _UNITS:
            tokens.append(ContentToken("unit", character, index, index + 1))
            index += 1
            continue
        if character in _IGNORED_PUNCTUATION:
            index += 1
            continue
        raise ValueError(
            f"unsupported visible character U+{ord(character):04X} at offset {index}"
        )
    return tuple(tokens)


def _is_han(character: str) -> bool:
    codepoint = ord(character)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0x20000 <= codepoint <= 0x2FA1F
    )


def _is_latin_letter(character: str) -> bool:
    return unicodedata.category(character).startswith("L") and "LATIN" in unicodedata.name(
        character, ""
    )
