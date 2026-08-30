"""Calculate independent Latin-word and Han-character quality metrics."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from quality_lab.calculate_token_metrics import (
    ExpectedContentUnit,
    TokenMetricCounts,
    calculate_token_metrics,
)
from quality_lab.tokenize_content_units import ContentToken


LANGUAGE_TOKEN_KIND_BY_TAG: Mapping[str, str] = MappingProxyType(
    {
        "en-US": "word",
        "zh-CN": "han",
    }
)


@dataclass(frozen=True, slots=True)
class LanguageTokenMetrics:
    """One requested language and its independently calculated token counts."""

    language: str
    metrics: TokenMetricCounts

    def __post_init__(self) -> None:
        if (
            type(self.language) is not str
            or self.language not in LANGUAGE_TOKEN_KIND_BY_TAG
        ):
            raise ValueError("language must be an exact supported Phase 1 tag")
        if type(self.metrics) is not TokenMetricCounts:
            raise TypeError("metrics must be an exact TokenMetricCounts value")


def calculate_language_token_metrics(
    expected: tuple[ExpectedContentUnit, ...],
    recognized: tuple[ContentToken, ...],
    languages: tuple[str, ...],
) -> tuple[LanguageTokenMetrics, ...]:
    """Project aggregate text into ordered, independent language channels.

    Phase 1 assigns Latin words to ``en-US`` and Han characters to ``zh-CN``.
    Numbers, signs, relations, operators, and units remain exclusively in the
    aggregate text and critical-value channels. Unmatched indexes in each
    returned score therefore use that filtered language channel's offsets.
    """

    if type(expected) is not tuple:
        raise TypeError("expected content units must be a tuple")
    if any(not isinstance(unit, ExpectedContentUnit) for unit in expected):
        raise TypeError("expected tuple contains a non-ExpectedContentUnit value")
    if type(recognized) is not tuple:
        raise TypeError("recognized content tokens must be a tuple")
    if any(type(token) is not ContentToken for token in recognized):
        raise TypeError("recognized tuple contains a non-ContentToken value")

    ordered_languages = _validate_languages(languages)
    results: list[LanguageTokenMetrics] = []
    for language in ordered_languages:
        token_kind = LANGUAGE_TOKEN_KIND_BY_TAG[language]
        expected_channel = tuple(unit for unit in expected if unit.kind == token_kind)
        if not expected_channel:
            raise ValueError(
                f"requested language {language!r} has no expected content units"
            )
        recognized_channel = tuple(
            token for token in recognized if token.kind == token_kind
        )
        results.append(
            LanguageTokenMetrics(
                language=language,
                metrics=calculate_token_metrics(
                    expected_channel,
                    recognized_channel,
                ),
            )
        )
    return tuple(results)


def _validate_languages(languages: object) -> tuple[str, ...]:
    if type(languages) is not tuple:
        raise TypeError("languages must be an exact ordered tuple")
    if not languages:
        raise ValueError("languages must contain at least one supported tag")
    if any(type(language) is not str for language in languages):
        raise TypeError("language tags must be exact strings")
    unsupported = tuple(
        language
        for language in languages
        if language not in LANGUAGE_TOKEN_KIND_BY_TAG
    )
    if unsupported:
        raise ValueError(f"unsupported Phase 1 language tag: {unsupported[0]!r}")
    if len(set(languages)) != len(languages):
        raise ValueError("languages must not contain duplicates")
    return languages
