"""Freeze Phase 1 per-fixture quality gates as exact rational values."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from quality_lab.rational_score import RationalScore


@dataclass(frozen=True, slots=True)
class FixtureThresholds:
    """Applicable channel thresholds for one fixture class."""

    text_recall: RationalScore | None = None
    content_precision: RationalScore | None = None
    formula_signature_accuracy: RationalScore | None = None
    formula_atom_precision: RationalScore | None = None
    table_data_accuracy: RationalScore | None = None
    critical_accuracy: RationalScore = RationalScore(1, 1)
    exact_table_headers: bool = False
    ordered_anchors_required: bool = False
    critical_slots_required: bool = False
    languages: tuple[str, ...] = ()


QUALITY_THRESHOLDS = MappingProxyType(
    {
        "printed_slide": FixtureThresholds(
            text_recall=RationalScore(95, 100),
            content_precision=RationalScore(90, 100),
            critical_slots_required=True,
            languages=("en-US", "zh-CN"),
        ),
        "degraded_printed_slide": FixtureThresholds(
            text_recall=RationalScore(95, 100),
            content_precision=RationalScore(90, 100),
            critical_slots_required=True,
            languages=("en-US", "zh-CN"),
        ),
        "handwriting": FixtureThresholds(
            text_recall=RationalScore(85, 100),
            content_precision=RationalScore(85, 100),
            critical_slots_required=True,
            languages=("en-US",),
        ),
        "formula_board": FixtureThresholds(
            text_recall=RationalScore(95, 100),
            content_precision=RationalScore(90, 100),
            formula_signature_accuracy=RationalScore(90, 100),
            formula_atom_precision=RationalScore(90, 100),
            critical_slots_required=True,
            languages=("en-US", "zh-CN"),
        ),
        "table": FixtureThresholds(
            text_recall=RationalScore(95, 100),
            content_precision=RationalScore(90, 100),
            table_data_accuracy=RationalScore(95, 100),
            exact_table_headers=True,
            languages=("en-US", "zh-CN"),
        ),
        "ordered_request": FixtureThresholds(
            text_recall=RationalScore(95, 100),
            content_precision=RationalScore(90, 100),
            formula_signature_accuracy=RationalScore(90, 100),
            formula_atom_precision=RationalScore(90, 100),
            ordered_anchors_required=True,
            critical_slots_required=True,
            languages=("en-US", "zh-CN"),
        ),
    }
)
