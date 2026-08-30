"""Apply the frozen Phase 1 thresholds and channel-specific hard gates."""

from __future__ import annotations

from quality_lab.calculate_token_metrics import TokenMetricCounts
from quality_lab.calculate_language_token_metrics import LanguageTokenMetrics
from quality_lab.phase1_quality_thresholds import QUALITY_THRESHOLDS
from quality_lab.score_critical_slots import CriticalSlotScore
from quality_lab.score_formula_signatures import FormulaScore
from quality_lab.score_ordered_anchors import OrderedAnchorScore
from quality_lab.score_table_cells import TableScore


_FAILURE_MESSAGE_BY_CODE = {
    "text_score_required": "text score is required",
    "text_recall_below_threshold": "text recall is below threshold",
    "content_precision_below_threshold": "content precision is below threshold",
    "text_critical_accuracy_below_one": "text critical accuracy is below 1.00",
    "text_unexpected_critical_units": "text contains unexpected critical units",
    "language_text_scores_required": "per-language text scores are required",
    "language_text_languages_mismatch": (
        "per-language text scores do not match the frozen languages"
    ),
    "critical_slot_score_required": "critical-slot score is required",
    "critical_slot_accuracy_below_one": "critical-slot accuracy is below 1.00",
    "critical_slot_duplicate_occurrences": (
        "critical slots contain duplicate occurrences"
    ),
    "critical_slot_score_not_applicable": (
        "critical-slot score is not applicable to this fixture class"
    ),
    "formula_score_required": "formula score is required",
    "formula_signature_accuracy_below_threshold": (
        "formula signature accuracy is below threshold"
    ),
    "formula_atom_precision_below_threshold": (
        "formula atom precision is below threshold"
    ),
    "formula_critical_accuracy_below_one": (
        "formula critical accuracy is below 1.00"
    ),
    "formula_unexpected_labels": "formula output contains unexpected labels",
    "formula_unexpected_atoms": "formula output contains unexpected atoms",
    "formula_score_not_applicable": (
        "formula score is not applicable to this fixture class"
    ),
    "table_score_required": "table score is required",
    "table_data_accuracy_below_threshold": (
        "table data-cell accuracy is below threshold"
    ),
    "table_critical_accuracy_below_one": (
        "table critical accuracy is below 1.00"
    ),
    "table_headers_not_exact": "table headers are not exact",
    "table_unexpected_data_coordinates": (
        "table contains unexpected data coordinates"
    ),
    "table_unexpected_critical_content": (
        "table contains unexpected critical cell content"
    ),
    "table_score_not_applicable": (
        "table score is not applicable to this fixture class"
    ),
    "ordered_anchor_score_required": "ordered-anchor score is required",
    "ordered_anchor_hard_gate_failed": "ordered-anchor hard gate failed",
    "ordered_anchor_score_not_applicable": (
        "ordered-anchor score is not applicable to this fixture class"
    ),
}


def quality_threshold_failures(
    fixture_class: str,
    *,
    text: TokenMetricCounts | None = None,
    language_text: tuple[LanguageTokenMetrics, ...] | None = None,
    critical_slots: CriticalSlotScore | None = None,
    formulas: FormulaScore | None = None,
    table: TableScore | None = None,
    anchors: OrderedAnchorScore | None = None,
) -> tuple[str, ...]:
    """Apply thresholds to scorer-built channels and return stable failures.

    Live evidence must enter through ``score_recognition_result`` so every
    channel and denominator is derived from the byte-frozen manifest. This
    metric-level helper deliberately does not accept a caller-owned manifest.
    """

    if type(fixture_class) is not str or fixture_class not in QUALITY_THRESHOLDS:
        raise ValueError(f"unknown Phase 1 fixture class: {fixture_class!r}")
    if text is not None and type(text) is not TokenMetricCounts:
        raise TypeError("text must be an exact TokenMetricCounts value")
    if language_text is not None and (
        type(language_text) is not tuple
        or any(type(item) is not LanguageTokenMetrics for item in language_text)
    ):
        raise TypeError(
            "language_text must be a tuple of exact LanguageTokenMetrics values"
        )
    if critical_slots is not None and type(critical_slots) is not CriticalSlotScore:
        raise TypeError("critical_slots must be an exact CriticalSlotScore value")
    if formulas is not None and type(formulas) is not FormulaScore:
        raise TypeError("formulas must be an exact FormulaScore value")
    if table is not None and type(table) is not TableScore:
        raise TypeError("table must be an exact TableScore value")
    if anchors is not None and type(anchors) is not OrderedAnchorScore:
        raise TypeError("anchors must be an exact OrderedAnchorScore value")
    thresholds = QUALITY_THRESHOLDS[fixture_class]
    failures: list[str] = []

    if thresholds.text_recall is not None or thresholds.content_precision is not None:
        if text is None:
            failures.append("text_score_required")
        else:
            if thresholds.text_recall is not None and not text.recall.meets(
                thresholds.text_recall
            ):
                failures.append("text_recall_below_threshold")
            if thresholds.content_precision is not None and not text.precision.meets(
                thresholds.content_precision
            ):
                failures.append("content_precision_below_threshold")
            if not text.critical_accuracy.meets(thresholds.critical_accuracy):
                failures.append("text_critical_accuracy_below_one")
            if text.unexpected_critical_indexes:
                failures.append("text_unexpected_critical_units")

    if thresholds.languages:
        if language_text is None:
            failures.append("language_text_scores_required")
        elif tuple(item.language for item in language_text) != thresholds.languages:
            failures.append("language_text_languages_mismatch")
        else:
            for item in language_text:
                if thresholds.text_recall is not None and not item.metrics.recall.meets(
                    thresholds.text_recall
                ):
                    failures.append(
                        f"language_text_recall_below_threshold:{item.language}"
                    )
                if (
                    thresholds.content_precision is not None
                    and not item.metrics.precision.meets(
                        thresholds.content_precision
                    )
                ):
                    failures.append(
                        f"language_content_precision_below_threshold:{item.language}"
                    )

    if not thresholds.critical_slots_required and critical_slots is not None:
        failures.append("critical_slot_score_not_applicable")
    elif thresholds.critical_slots_required and critical_slots is None:
        failures.append("critical_slot_score_required")
    elif critical_slots is not None:
        if not critical_slots.accuracy.meets(thresholds.critical_accuracy):
            failures.append("critical_slot_accuracy_below_one")
        if critical_slots.duplicate_occurrence_count:
            failures.append("critical_slot_duplicate_occurrences")

    if thresholds.formula_signature_accuracy is None and formulas is not None:
        failures.append("formula_score_not_applicable")
    elif thresholds.formula_signature_accuracy is not None:
        if formulas is None:
            failures.append("formula_score_required")
        else:
            if not formulas.signature_accuracy.meets(
                thresholds.formula_signature_accuracy
            ):
                failures.append("formula_signature_accuracy_below_threshold")
            if (
                thresholds.formula_atom_precision is not None
                and not formulas.atom_precision.meets(thresholds.formula_atom_precision)
            ):
                failures.append("formula_atom_precision_below_threshold")
            if not formulas.critical_accuracy.meets(thresholds.critical_accuracy):
                failures.append("formula_critical_accuracy_below_one")
            if formulas.unexpected_labels:
                failures.append("formula_unexpected_labels")
            if formulas.unexpected_atom_count:
                failures.append("formula_unexpected_atoms")

    if thresholds.table_data_accuracy is None and table is not None:
        failures.append("table_score_not_applicable")
    elif thresholds.table_data_accuracy is not None:
        if table is None:
            failures.append("table_score_required")
        else:
            if not table.data_cell_accuracy.meets(thresholds.table_data_accuracy):
                failures.append("table_data_accuracy_below_threshold")
            if not table.critical_accuracy.meets(thresholds.critical_accuracy):
                failures.append("table_critical_accuracy_below_one")
            if thresholds.exact_table_headers and (
                table.header_accuracy.numerator != table.header_accuracy.denominator
            ):
                failures.append("table_headers_not_exact")
            if table.unexpected_coordinate_count:
                failures.append("table_unexpected_data_coordinates")
            if table.unexpected_critical_cell_count:
                failures.append("table_unexpected_critical_content")

    if not thresholds.ordered_anchors_required and anchors is not None:
        failures.append("ordered_anchor_score_not_applicable")
    elif thresholds.ordered_anchors_required:
        if anchors is None:
            failures.append("ordered_anchor_score_required")
        elif not anchors.passes:
            failures.append("ordered_anchor_hard_gate_failed")

    return tuple(failures)


def assert_quality_thresholds(
    fixture_class: str,
    *,
    text: TokenMetricCounts | None = None,
    language_text: tuple[LanguageTokenMetrics, ...] | None = None,
    critical_slots: CriticalSlotScore | None = None,
    formulas: FormulaScore | None = None,
    table: TableScore | None = None,
    anchors: OrderedAnchorScore | None = None,
) -> None:
    """Raise one deterministic assertion for scorer-built metric channels."""

    failures = quality_threshold_failures(
        fixture_class,
        text=text,
        language_text=language_text,
        critical_slots=critical_slots,
        formulas=formulas,
        table=table,
        anchors=anchors,
    )
    if failures:
        raise AssertionError(
            "; ".join(_failure_message(code) for code in failures)
        )


def _failure_message(code: str) -> str:
    if code.startswith("language_text_recall_below_threshold:"):
        language = code.partition(":")[2]
        return f"{language} text recall is below threshold"
    if code.startswith("language_content_precision_below_threshold:"):
        language = code.partition(":")[2]
        return f"{language} content precision is below threshold"
    return _FAILURE_MESSAGE_BY_CODE[code]
