"""Serialize one integrated quality report without floats or hidden fields."""

from __future__ import annotations

from quality_lab.rational_score import RationalScore
from quality_lab.score_recognition_result import RecognitionQualityReport


def serialize_recognition_quality_report(
    report: RecognitionQualityReport,
) -> dict[str, object]:
    """Return the complete JSON-safe evidence view of one integrated report."""

    if type(report) is not RecognitionQualityReport:
        raise TypeError("report must be an exact RecognitionQualityReport")
    return {
        "target": report.target,
        "profile": report.profile,
        "dispatch_sequence": report.dispatch_sequence,
        "fixture_ids": list(report.fixture_ids),
        "text": {
            "recall": _score(report.text_score.recall),
            "precision": _score(report.text_score.precision),
            "critical_accuracy": _score(report.text_score.critical_accuracy),
            "unmatched_recognized_indexes": list(
                report.text_score.unmatched_recognized_indexes
            ),
            "unexpected_critical_indexes": list(
                report.text_score.unexpected_critical_indexes
            ),
        },
        "languages": [
            {
                "language": item.language,
                "recall": _score(item.metrics.recall),
                "precision": _score(item.metrics.precision),
                "critical_accuracy": _score(item.metrics.critical_accuracy),
                "unmatched_recognized_indexes": list(
                    item.metrics.unmatched_recognized_indexes
                ),
                "unexpected_critical_indexes": list(
                    item.metrics.unexpected_critical_indexes
                ),
            }
            for item in report.language_text_scores
        ],
        "critical_slots": (
            None
            if report.critical_slot_score is None
            else {
                "accuracy": _score(report.critical_slot_score.accuracy),
                "missing_slot_ids": list(
                    report.critical_slot_score.missing_slot_ids
                ),
                "duplicate_occurrence_count": (
                    report.critical_slot_score.duplicate_occurrence_count
                ),
            }
        ),
        "formulas": (
            None
            if report.formula_score is None
            else {
                "signature_accuracy": _score(
                    report.formula_score.signature_accuracy
                ),
                "atom_precision": _score(report.formula_score.atom_precision),
                "critical_accuracy": _score(
                    report.formula_score.critical_accuracy
                ),
                "missing_labels": list(report.formula_score.missing_labels),
                "unexpected_labels": list(report.formula_score.unexpected_labels),
                "missing_atom_count": report.formula_score.missing_atom_count,
                "unexpected_atom_count": report.formula_score.unexpected_atom_count,
            }
        ),
        "table": (
            None
            if report.table_score is None
            else {
                "header_accuracy": _score(report.table_score.header_accuracy),
                "data_cell_accuracy": _score(
                    report.table_score.data_cell_accuracy
                ),
                "critical_accuracy": _score(report.table_score.critical_accuracy),
                "unexpected_coordinate_count": (
                    report.table_score.unexpected_coordinate_count
                ),
                "unexpected_critical_cell_count": (
                    report.table_score.unexpected_critical_cell_count
                ),
            }
        ),
        "ordered_anchors": (
            None
            if report.ordered_anchor_score is None
            else {
                "presence": _score(report.ordered_anchor_score.presence),
                "first_token_offsets": list(
                    report.ordered_anchor_score.first_token_offsets
                ),
                "first_appearances_in_order": (
                    report.ordered_anchor_score.first_appearances_in_order
                ),
                "anchors_do_not_overlap": (
                    report.ordered_anchor_score.anchors_do_not_overlap
                ),
                "source_order_matches": (
                    report.ordered_anchor_score.source_order_matches
                ),
                "image_count_matches": (
                    report.ordered_anchor_score.image_count_matches
                ),
                "duplicate_occurrence_count": (
                    report.ordered_anchor_score.duplicate_occurrence_count
                ),
            }
        ),
        "failure_codes": list(report.failures),
        "passes": report.passes,
    }


def _score(value: RationalScore) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}
