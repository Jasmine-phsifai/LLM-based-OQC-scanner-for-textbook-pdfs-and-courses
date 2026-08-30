from __future__ import annotations

import pytest

from quality_lab.build_scorer_expectations import build_scorer_expectations
from quality_lab.load_fixture_manifest import load_fixture_manifest


def test_builds_every_typed_fixture_and_ordered_channel() -> None:
    manifest = load_fixture_manifest()

    expectations = build_scorer_expectations(manifest)

    assert tuple(item.fixture_id for item in expectations.fixtures) == tuple(
        fixture.id for fixture in manifest.fixtures
    )
    by_id = {item.fixture_id: item for item in expectations.fixtures}
    assert len(by_id["formula-integrity-board"].formulas) == 12
    assert by_id["formula-integrity-board"].table is None
    assert by_id["calibration-data-table"].table is not None
    assert len(by_id["calibration-data-table"].table.header) == 6
    assert len(by_id["calibration-data-table"].table.rows) == 5
    assert tuple(item.request_id for item in expectations.ordered_requests) == (
        "clean-slide-then-formula-board",
    )
    assert tuple(
        anchor.source_index for anchor in expectations.ordered_requests[0].anchors
    ) == (0, 1)
    ordered = expectations.ordered_requests[0]
    assert ordered.text
    assert len(ordered.critical_slots) == 10
    assert len(ordered.formulas) == 12
    assert ordered.table is None


def test_aggregates_repeated_handwriting_tokens_into_exact_counts() -> None:
    manifest = load_fixture_manifest()
    expectations = build_scorer_expectations(manifest)
    handwriting = next(
        item for item in expectations.fixtures if item.fixture_id == "handwritten-whiteboard"
    )
    by_value = {unit.accepted[0]: unit for unit in handwriting.text}
    precision_by_value = {
        unit.accepted[0]: unit for unit in handwriting.precision_text
    }

    assert by_value["End"].count == 2
    assert by_value["+"].count == 2
    assert sum(unit.count for unit in handwriting.text) == 30
    assert sum(unit.count for unit in handwriting.precision_text) == 48
    assert precision_by_value["R"].count == 2
    assert precision_by_value["3"].count == 4
    assert precision_by_value["RG"].count == 2
    assert len([unit for unit in handwriting.text if unit.accepted == ("End",)]) == 1
    assert len([unit for unit in handwriting.text if unit.accepted == ("+",)]) == 1


def test_rejects_non_manifest_input() -> None:
    with pytest.raises(TypeError, match="exact Phase1FixtureManifest"):
        build_scorer_expectations(object())  # type: ignore[arg-type]
