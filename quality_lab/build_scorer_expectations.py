"""Build scorer-native expectations from one validated Phase 1 manifest."""

from __future__ import annotations

from dataclasses import dataclass

from quality_lab.calculate_token_metrics import ExpectedContentUnit
from quality_lab.fixture_manifest import (
    FixtureRecord,
    OrderedRequestRecord,
    Phase1FixtureManifest,
    ScoredContentUnit,
    TableExpectation,
)
from quality_lab.score_critical_slots import ExpectedCriticalSlot
from quality_lab.score_formula_signatures import ExpectedFormula
from quality_lab.score_ordered_anchors import OrderedAnchor
from quality_lab.score_table_cells import ExpectedMarkdownTable, ExpectedTableCell
from quality_lab.tokenize_content_units import tokenize_content_units


@dataclass(frozen=True, slots=True)
class FixtureScorerExpectations:
    """All applicable typed scorer channels for one fixture."""

    fixture_id: str
    text: tuple[ExpectedContentUnit, ...]
    precision_text: tuple[ExpectedContentUnit, ...]
    critical_slots: tuple[ExpectedCriticalSlot, ...]
    formulas: tuple[ExpectedFormula, ...]
    table: ExpectedMarkdownTable | None


@dataclass(frozen=True, slots=True)
class OrderedRequestScorerExpectations:
    """Combined typed content plus anchors for one multi-image request."""

    request_id: str
    fixture_ids: tuple[str, ...]
    text: tuple[ExpectedContentUnit, ...]
    precision_text: tuple[ExpectedContentUnit, ...]
    critical_slots: tuple[ExpectedCriticalSlot, ...]
    formulas: tuple[ExpectedFormula, ...]
    table: ExpectedMarkdownTable | None
    anchors: tuple[OrderedAnchor, ...]


@dataclass(frozen=True, slots=True)
class Phase1ScorerExpectations:
    """Scorer-native fixture and ordered-request records."""

    fixtures: tuple[FixtureScorerExpectations, ...]
    ordered_requests: tuple[OrderedRequestScorerExpectations, ...]


def build_scorer_expectations(
    manifest: Phase1FixtureManifest,
) -> Phase1ScorerExpectations:
    """Map manifest truth once, aggregating repeated atomic text occurrences."""

    if type(manifest) is not Phase1FixtureManifest:
        raise TypeError("manifest must be an exact Phase1FixtureManifest")
    fixtures = tuple(
        _build_fixture_expectations(fixture) for fixture in manifest.fixtures
    )
    fixtures_by_id = {fixture.fixture_id: fixture for fixture in fixtures}
    return Phase1ScorerExpectations(
        fixtures=fixtures,
        ordered_requests=tuple(
            _build_ordered_request_expectations(
                request,
                fixtures_by_id=fixtures_by_id,
            )
            for request in manifest.ordered_requests
        ),
    )


def _build_fixture_expectations(fixture: FixtureRecord) -> FixtureScorerExpectations:
    return FixtureScorerExpectations(
        fixture_id=fixture.id,
        text=_build_text_expectations(fixture.id, fixture.content_units),
        precision_text=_build_text_expectations(
            f"{fixture.id}-precision",
            fixture.content_units + fixture.optional_content_units,
        ),
        critical_slots=tuple(
            ExpectedCriticalSlot(
                id=slot.id,
                accepted=slot.accepted,
                case_sensitive=slot.case_sensitive,
            )
            for slot in fixture.critical_slots
        ),
        formulas=tuple(
            ExpectedFormula(
                label=formula.label,
                accepted_latex=formula.accepted_latex,
            )
            for formula in fixture.formulas
        ),
        table=(
            _build_table_expectation(fixture.table)
            if fixture.table is not None
            else None
        ),
    )


def _build_text_expectations(
    fixture_id: str,
    units: tuple[ScoredContentUnit, ...],
) -> tuple[ExpectedContentUnit, ...]:
    grouped: dict[tuple[str, str, bool], tuple[str, str, int, bool]] = {}
    for unit in units:
        tokens = tokenize_content_units(unit.text)
        if not tokens:
            raise ValueError(f"content unit {unit.id!r} has no scored token")
        for token in tokens:
            value = token.value if unit.case_sensitive else token.value.casefold()
            key = (token.kind, value, unit.case_sensitive)
            existing = grouped.get(key)
            if existing is None:
                grouped[key] = (token.kind, token.value, 1, unit.case_sensitive)
            else:
                grouped[key] = (
                    existing[0],
                    existing[1],
                    existing[2] + 1,
                    existing[3],
                )
    return tuple(
        ExpectedContentUnit(
            id=f"{fixture_id}-token-{index:04d}",
            kind=kind,
            accepted=(accepted,),
            count=count,
            case_sensitive=case_sensitive,
        )
        for index, (kind, accepted, count, case_sensitive) in enumerate(grouped.values())
    )


def _build_table_expectation(table: TableExpectation) -> ExpectedMarkdownTable:
    cells_by_coordinate = {(cell.row, cell.column): cell for cell in table.cells}
    return ExpectedMarkdownTable(
        header=tuple(
            ExpectedTableCell(
                accepted=header.accepted,
                case_sensitive=header.case_sensitive,
            )
            for header in table.headers
        ),
        rows=tuple(
            tuple(
                ExpectedTableCell(
                    accepted=cells_by_coordinate[(row, column)].accepted,
                    case_sensitive=cells_by_coordinate[(row, column)].case_sensitive,
                    critical=cells_by_coordinate[(row, column)].critical,
                )
                for column in range(table.column_count)
            )
            for row in range(table.row_count)
        ),
    )


def _build_ordered_request_expectations(
    request: OrderedRequestRecord,
    *,
    fixtures_by_id: dict[str, FixtureScorerExpectations],
) -> OrderedRequestScorerExpectations:
    source_expectations = tuple(
        fixtures_by_id[fixture_id] for fixture_id in request.fixture_ids
    )
    tables = tuple(
        expectation.table
        for expectation in source_expectations
        if expectation.table is not None
    )
    if tables:
        raise ValueError("the frozen ordered request must not contain a table fixture")
    return OrderedRequestScorerExpectations(
        request_id=request.id,
        fixture_ids=request.fixture_ids,
        text=_aggregate_expected_text(
            request.id,
            tuple(
                unit
                for expectation in source_expectations
                for unit in expectation.text
            ),
        ),
        precision_text=_aggregate_expected_text(
            f"{request.id}-precision",
            tuple(
                unit
                for expectation in source_expectations
                for unit in expectation.precision_text
            ),
        ),
        critical_slots=tuple(
            ExpectedCriticalSlot(
                id=f"{expectation.fixture_id}-{slot.id}",
                accepted=slot.accepted,
                count=slot.count,
                case_sensitive=slot.case_sensitive,
            )
            for expectation in source_expectations
            for slot in expectation.critical_slots
        ),
        formulas=tuple(
            formula
            for expectation in source_expectations
            for formula in expectation.formulas
        ),
        table=None,
        anchors=tuple(
            OrderedAnchor(
                id=anchor.id,
                source_index=anchor.source_index,
                accepted=anchor.accepted,
                case_sensitive=anchor.case_sensitive,
            )
            for anchor in request.anchors
        ),
    )


def _aggregate_expected_text(
    request_id: str,
    units: tuple[ExpectedContentUnit, ...],
) -> tuple[ExpectedContentUnit, ...]:
    grouped: dict[
        tuple[str, tuple[str, ...], bool, bool],
        int,
    ] = {}
    for unit in units:
        key = (unit.kind, unit.accepted, unit.case_sensitive, unit.critical)
        grouped[key] = grouped.get(key, 0) + unit.count
    return tuple(
        ExpectedContentUnit(
            id=f"{request_id}-token-{index:04d}",
            kind=kind,
            accepted=accepted,
            count=count,
            case_sensitive=case_sensitive,
            critical=critical,
        )
        for index, (
            (kind, accepted, case_sensitive, critical),
            count,
        ) in enumerate(grouped.items())
    )
