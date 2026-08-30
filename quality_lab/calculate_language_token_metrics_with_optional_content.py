"""Project optional-aware text scores into independent language channels."""

from __future__ import annotations

from quality_lab.calculate_language_token_metrics import (
    LanguageTokenMetrics,
    calculate_language_token_metrics,
)
from quality_lab.calculate_token_metrics import ExpectedContentUnit, TokenMetricCounts
from quality_lab.calculate_token_metrics_with_optional_content import (
    calculate_token_metrics_with_optional_content,
)
from quality_lab.tokenize_content_units import ContentToken


def calculate_language_token_metrics_with_optional_content(
    required: tuple[ExpectedContentUnit, ...],
    precision_truth: tuple[ExpectedContentUnit, ...],
    recognized: tuple[ContentToken, ...],
    languages: tuple[str, ...],
) -> tuple[LanguageTokenMetrics, ...]:
    """Keep required recall and source-complete precision per language."""

    calculate_token_metrics_with_optional_content(
        required,
        precision_truth,
        recognized,
    )
    required_scores = calculate_language_token_metrics(
        required,
        recognized,
        languages,
    )
    precision_scores = calculate_language_token_metrics(
        precision_truth,
        recognized,
        languages,
    )
    return tuple(
        LanguageTokenMetrics(
            language=required_item.language,
            metrics=TokenMetricCounts(
                recall=required_item.metrics.recall,
                precision=precision_item.metrics.precision,
                critical_accuracy=required_item.metrics.critical_accuracy,
                unmatched_recognized_indexes=(
                    precision_item.metrics.unmatched_recognized_indexes
                ),
                unexpected_critical_indexes=(
                    precision_item.metrics.unexpected_critical_indexes
                ),
            ),
        )
        for required_item, precision_item in zip(
            required_scores,
            precision_scores,
            strict=True,
        )
    )
