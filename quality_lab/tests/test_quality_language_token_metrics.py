from __future__ import annotations

from types import MappingProxyType

import pytest

from quality_lab.build_scorer_expectations import build_scorer_expectations
from quality_lab.calculate_language_token_metrics import (
    LANGUAGE_TOKEN_KIND_BY_TAG,
    calculate_language_token_metrics,
)
from quality_lab.calculate_token_metrics import (
    ExpectedContentUnit,
    calculate_token_metrics,
)
from quality_lab.load_fixture_manifest import load_fixture_manifest
from quality_lab.rational_score import RationalScore
from quality_lab.tokenize_content_units import tokenize_content_units


def test_language_token_kind_mapping_is_exact_and_immutable() -> None:
    assert isinstance(LANGUAGE_TOKEN_KIND_BY_TAG, MappingProxyType)
    assert tuple(LANGUAGE_TOKEN_KIND_BY_TAG.items()) == (
        ("en-US", "word"),
        ("zh-CN", "han"),
    )
    with pytest.raises(TypeError):
        LANGUAGE_TOKEN_KIND_BY_TAG["en-US"] = "han"  # type: ignore[index]


def test_language_gate_exposes_han_loss_hidden_by_aggregate_recall() -> None:
    manifest = load_fixture_manifest()
    fixture = next(
        fixture
        for fixture in manifest.fixtures
        if fixture.fixture_class == "printed_slide"
    )
    expected = next(
        item
        for item in build_scorer_expectations(manifest).fixtures
        if item.fixture_id == fixture.id
    ).text
    recognized_text, removed_count = _remove_first_han_characters(
        "\n".join(unit.text for unit in fixture.content_units),
        count=10,
    )
    recognized = tokenize_content_units(recognized_text)

    aggregate = calculate_token_metrics(expected, recognized)
    by_language = {
        score.language: score.metrics
        for score in calculate_language_token_metrics(
            expected,
            recognized,
            fixture.languages,
        )
    }

    threshold = RationalScore(95, 100)
    assert removed_count == 10
    assert aggregate.recall == RationalScore(302, 312)
    assert aggregate.recall.meets(threshold)
    assert by_language["en-US"].recall.numerator == (
        by_language["en-US"].recall.denominator
    )
    assert by_language["zh-CN"].recall == RationalScore(166, 176)
    assert not by_language["zh-CN"].recall.meets(threshold)


def test_languages_are_scored_independently_and_keep_requested_order() -> None:
    expected = (
        ExpectedContentUnit("english", "word", ("Alpha",)),
        ExpectedContentUnit("chinese", "han", ("中",)),
        ExpectedContentUnit("global-number", "number", ("7",)),
    )
    recognized = tokenize_content_units("中 7")

    scores = calculate_language_token_metrics(
        expected,
        recognized,
        ("zh-CN", "en-US"),
    )

    assert tuple(score.language for score in scores) == ("zh-CN", "en-US")
    assert scores[0].metrics.recall == RationalScore(1, 1)
    assert scores[0].metrics.precision == RationalScore(1, 1)
    assert scores[1].metrics.recall == RationalScore(0, 1)
    assert scores[1].metrics.precision == RationalScore(0, 1)


def test_language_precision_counts_only_extras_in_its_own_text_channel() -> None:
    expected = (
        ExpectedContentUnit("english", "word", ("Alpha",)),
        ExpectedContentUnit("chinese", "han", ("中",)),
        ExpectedContentUnit("global-number", "number", ("7",)),
    )
    recognized = tokenize_content_units("Alpha Beta 中文 7 999")

    scores = {
        score.language: score.metrics
        for score in calculate_language_token_metrics(
            expected,
            recognized,
            ("en-US", "zh-CN"),
        )
    }
    aggregate = calculate_token_metrics(expected, recognized)

    assert scores["en-US"].recall == RationalScore(1, 1)
    assert scores["en-US"].precision == RationalScore(1, 2)
    assert scores["en-US"].unmatched_recognized_indexes == (1,)
    assert scores["zh-CN"].recall == RationalScore(1, 1)
    assert scores["zh-CN"].precision == RationalScore(1, 2)
    assert scores["zh-CN"].unmatched_recognized_indexes == (1,)
    assert aggregate.precision == RationalScore(3, 6)
    assert aggregate.unexpected_critical_indexes


@pytest.mark.parametrize(
    ("languages", "error", "message"),
    (
        (["en-US"], TypeError, "exact ordered tuple"),
        ((), ValueError, "at least one"),
        (("en-US", "en-US"), ValueError, "duplicates"),
        (("fr-FR",), ValueError, "unsupported"),
        ((1,), TypeError, "exact strings"),
    ),
)
def test_invalid_language_requests_fail_closed(languages, error, message) -> None:
    expected = (ExpectedContentUnit("english", "word", ("Alpha",)),)
    recognized = tokenize_content_units("Alpha")

    with pytest.raises(error, match=message):
        calculate_language_token_metrics(
            expected,
            recognized,
            languages,
        )


def test_requested_language_requires_expected_units() -> None:
    expected = (
        ExpectedContentUnit("english", "word", ("Alpha",)),
        ExpectedContentUnit("global-number", "number", ("7",)),
    )

    with pytest.raises(ValueError, match="zh-CN.*no expected"):
        calculate_language_token_metrics(
            expected,
            tokenize_content_units("Alpha 7"),
            ("en-US", "zh-CN"),
        )


def _remove_first_han_characters(value: str, *, count: int) -> tuple[str, int]:
    kept: list[str] = []
    removed = 0
    for character in value:
        codepoint = ord(character)
        is_han = 0x3400 <= codepoint <= 0x4DBF or 0x4E00 <= codepoint <= 0x9FFF
        if is_han and removed < count:
            removed += 1
            continue
        kept.append(character)
    return "".join(kept), removed
