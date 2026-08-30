"""Score one recognized Markdown result from its exact manifest dispatch."""

from __future__ import annotations

from dataclasses import dataclass

from quality_lab.assert_quality_thresholds import quality_threshold_failures
from quality_lab.build_scorer_expectations import (
    FixtureScorerExpectations,
    build_scorer_expectations,
)
from quality_lab.build_scoring_views import build_scoring_views
from quality_lab.calculate_language_token_metrics import (
    LanguageTokenMetrics,
)
from quality_lab.calculate_language_token_metrics_with_optional_content import (
    calculate_language_token_metrics_with_optional_content,
)
from quality_lab.calculate_token_metrics import (
    ExpectedContentUnit,
    TokenMetricCounts,
)
from quality_lab.calculate_token_metrics_with_optional_content import (
    calculate_token_metrics_with_optional_content,
)
from quality_lab.fixture_manifest import (
    FixtureRecord,
    LiveDispatchRecord,
    NeutralMarkdownRules,
    OrderedRequestRecord,
    Phase1FixtureManifest,
)
from quality_lab.normalize_recognized_markdown_v2 import (
    normalize_recognized_markdown_v2,
)
from quality_lab.normalize_recognized_markdown_v3 import (
    normalize_recognized_markdown_v3,
)
from quality_lab.normalize_recognized_markdown_v4 import (
    normalize_recognized_markdown_v4,
)
from quality_lab.normalize_recognized_markdown_v5 import (
    normalize_recognized_markdown_v5,
)
from quality_lab.normalize_recognized_markdown_v6 import (
    normalize_recognized_markdown_v6,
)
from quality_lab.normalize_recognized_markdown_v7 import (
    normalize_recognized_markdown_v7,
)
from quality_lab.score_critical_slots import (
    CriticalSlotScore,
    ExpectedCriticalSlot,
    score_critical_slots,
)
from quality_lab.score_formula_signatures import (
    ExpectedFormula,
    FormulaScore,
    score_formula_signatures,
)
from quality_lab.score_ordered_anchors import (
    OrderedAnchor,
    OrderedAnchorScore,
    score_ordered_anchors,
)
from quality_lab.score_table_cells import (
    ExpectedMarkdownTable,
    TableScore,
    score_table_cells,
)
from quality_lab.tokenize_content_units import tokenize_content_units


@dataclass(frozen=True, slots=True)
class RecognitionQualityReport:
    """Every applicable typed score for one immutable live-dispatch target."""

    target: str
    profile: str
    dispatch_sequence: int
    fixture_ids: tuple[str, ...]
    text_score: TokenMetricCounts
    language_text_scores: tuple[LanguageTokenMetrics, ...]
    critical_slot_score: CriticalSlotScore | None
    formula_score: FormulaScore | None
    table_score: TableScore | None
    ordered_anchor_score: OrderedAnchorScore | None
    failures: tuple[str, ...]
    passes: bool

    def __post_init__(self) -> None:
        if type(self.target) is not str or not self.target:
            raise ValueError("report target must be nonempty exact text")
        if type(self.profile) is not str or not self.profile:
            raise ValueError("report profile must be nonempty exact text")
        if type(self.dispatch_sequence) is not int or self.dispatch_sequence < 0:
            raise ValueError("report dispatch_sequence must be non-negative")
        if type(self.fixture_ids) is not tuple or not self.fixture_ids or any(
            type(value) is not str or not value for value in self.fixture_ids
        ):
            raise TypeError("report fixture_ids must be nonempty exact text")
        if type(self.text_score) is not TokenMetricCounts:
            raise TypeError("report text_score must be exact TokenMetricCounts")
        if type(self.language_text_scores) is not tuple or any(
            type(value) is not LanguageTokenMetrics
            for value in self.language_text_scores
        ):
            raise TypeError("report language scores must be exact typed values")
        for value, expected_type, field_name in (
            (self.critical_slot_score, CriticalSlotScore, "critical_slot_score"),
            (self.formula_score, FormulaScore, "formula_score"),
            (self.table_score, TableScore, "table_score"),
            (self.ordered_anchor_score, OrderedAnchorScore, "ordered_anchor_score"),
        ):
            if value is not None and type(value) is not expected_type:
                raise TypeError(f"report {field_name} has the wrong exact type")
        if type(self.failures) is not tuple or any(
            type(value) is not str or not value for value in self.failures
        ):
            raise TypeError("report failures must be an exact text tuple")
        if type(self.passes) is not bool:
            raise TypeError("report passes must be an exact boolean")
        if self.passes is bool(self.failures):
            raise ValueError("report passes must be the inverse of its failures")


@dataclass(frozen=True, slots=True)
class _ResolvedScoringTarget:
    target: str
    profile: str
    languages: tuple[str, ...]
    neutral_markdown: tuple[str, ...]
    text: tuple[ExpectedContentUnit, ...]
    precision_text: tuple[ExpectedContentUnit, ...]
    critical_slots: tuple[ExpectedCriticalSlot, ...]
    formulas: tuple[ExpectedFormula, ...]
    table: ExpectedMarkdownTable | None
    anchors: tuple[OrderedAnchor, ...]


def score_recognition_result(
    manifest: Phase1FixtureManifest,
    dispatch: LiveDispatchRecord,
    recognized_markdown: str,
) -> RecognitionQualityReport:
    """Build and apply every score declared by one attached manifest dispatch."""

    _require_attached_dispatch(manifest, dispatch)
    if type(recognized_markdown) is not str or not recognized_markdown.strip():
        raise ValueError("recognized_markdown must be nonempty plain text")

    target = _resolve_scoring_target(manifest, dispatch)
    if manifest.scoring_contract.formula_dialect == "labeled-latex-restricted.v7":
        scoring_markdown = normalize_recognized_markdown_v7(recognized_markdown)
    elif manifest.scoring_contract.formula_dialect == "labeled-latex-restricted.v6":
        scoring_markdown = normalize_recognized_markdown_v6(recognized_markdown)
    elif manifest.scoring_contract.formula_dialect == "labeled-latex-restricted.v5":
        scoring_markdown = normalize_recognized_markdown_v5(recognized_markdown)
    elif manifest.scoring_contract.formula_dialect == "labeled-latex-restricted.v4":
        scoring_markdown = normalize_recognized_markdown_v4(recognized_markdown)
    elif manifest.scoring_contract.formula_dialect == "labeled-latex-restricted.v3":
        scoring_markdown = normalize_recognized_markdown_v3(recognized_markdown)
    elif manifest.scoring_contract.formula_dialect == "labeled-latex-restricted.v2":
        scoring_markdown = normalize_recognized_markdown_v2(recognized_markdown)
    else:
        scoring_markdown = recognized_markdown
    views = build_scoring_views(
        scoring_markdown,
        neutral_markdown=target.neutral_markdown,
    )
    recognized_text_tokens = tokenize_content_units(views.text)
    text_score = calculate_token_metrics_with_optional_content(
        target.text,
        target.precision_text,
        recognized_text_tokens,
    )
    language_text_scores = calculate_language_token_metrics_with_optional_content(
        target.text,
        target.precision_text,
        recognized_text_tokens,
        target.languages,
    )
    critical_slot_score = (
        score_critical_slots(target.critical_slots, views.text)
        if target.critical_slots
        else None
    )
    formula_score = _score_formula_view(target.formulas, views.formulas)
    table_score = _score_table_view(target.table, views.table)
    ordered_anchor_score = (
        score_ordered_anchors(
            target.anchors,
            views.anchors,
            actual_source_indices=tuple(range(len(dispatch.fixture_ids))),
            actual_image_count=len(dispatch.fixture_ids),
        )
        if target.anchors
        else None
    )
    failures = quality_threshold_failures(
        target.profile,
        text=text_score,
        language_text=language_text_scores,
        critical_slots=critical_slot_score,
        formulas=formula_score,
        table=table_score,
        anchors=ordered_anchor_score,
    )
    return RecognitionQualityReport(
        target=target.target,
        profile=target.profile,
        dispatch_sequence=dispatch.sequence,
        fixture_ids=dispatch.fixture_ids,
        text_score=text_score,
        language_text_scores=language_text_scores,
        critical_slot_score=critical_slot_score,
        formula_score=formula_score,
        table_score=table_score,
        ordered_anchor_score=ordered_anchor_score,
        failures=failures,
        passes=not failures,
    )


def _require_attached_dispatch(
    manifest: Phase1FixtureManifest,
    dispatch: LiveDispatchRecord,
) -> None:
    if type(manifest) is not Phase1FixtureManifest:
        raise TypeError("manifest must be an exact Phase1FixtureManifest")
    _require_canonical_manifest(manifest)
    if type(dispatch) is not LiveDispatchRecord:
        raise TypeError("dispatch must be an exact LiveDispatchRecord")
    dispatches = manifest.live_dispatch_order
    if type(dispatches) is not tuple or any(
        type(item) is not LiveDispatchRecord for item in dispatches
    ):
        raise TypeError("manifest live_dispatch_order must contain exact records")
    if tuple(item.sequence for item in dispatches) != tuple(range(len(dispatches))):
        raise ValueError("manifest dispatch sequence must be contiguous from zero")
    if type(dispatch.sequence) is not int or not 0 <= dispatch.sequence < len(dispatches):
        raise ValueError("dispatch sequence is outside the manifest dispatch order")
    if dispatches[dispatch.sequence] is not dispatch:
        raise ValueError(
            "dispatch must be the exact manifest record at its declared sequence"
        )
    if type(dispatch.kind) is not str or dispatch.kind not in {"single", "ordered"}:
        raise ValueError("dispatch kind must be 'single' or 'ordered'")
    if (
        type(dispatch.fixture_ids) is not tuple
        or not dispatch.fixture_ids
        or any(type(value) is not str or not value for value in dispatch.fixture_ids)
        or len(set(dispatch.fixture_ids)) != len(dispatch.fixture_ids)
    ):
        raise ValueError("dispatch fixture_ids must be unique nonempty strings")
    if dispatch.ordered_request_id is not None and (
        type(dispatch.ordered_request_id) is not str
        or not dispatch.ordered_request_id
    ):
        raise ValueError("dispatch ordered_request_id must be null or nonempty text")


def _require_canonical_manifest(manifest: Phase1FixtureManifest) -> None:
    """Reject dataclass mutations that retain the committed raw hash fields."""

    # Local import keeps the loader free to validate its own scorer dependencies
    # without making this module part of its import-time dependency graph.
    from quality_lab.load_fixture_manifest import load_fixture_manifest

    canonical_manifest = load_fixture_manifest()
    if manifest != canonical_manifest:
        raise ValueError(
            "manifest differs from the freshly strict-loaded canonical manifest"
        )


def _resolve_scoring_target(
    manifest: Phase1FixtureManifest,
    dispatch: LiveDispatchRecord,
) -> _ResolvedScoringTarget:
    expectations = build_scorer_expectations(manifest)
    fixture_records = _unique_fixtures(manifest)
    fixture_expectations = _unique_fixture_expectations(expectations.fixtures)
    neutral_rules = _unique_neutral_rules(manifest)

    if dispatch.kind == "single":
        if len(dispatch.fixture_ids) != 1 or dispatch.ordered_request_id is not None:
            raise ValueError("single dispatch must identify exactly one fixture")
        fixture_id = dispatch.fixture_ids[0]
        fixture = fixture_records.get(fixture_id)
        expected = fixture_expectations.get(fixture_id)
        if fixture is None or expected is None:
            raise ValueError("single dispatch references an unknown fixture")
        profile = fixture.fixture_class
        return _ResolvedScoringTarget(
            target=fixture.id,
            profile=profile,
            languages=fixture.languages,
            neutral_markdown=_rules_for_profile(neutral_rules, profile),
            text=expected.text,
            precision_text=expected.precision_text,
            critical_slots=expected.critical_slots,
            formulas=expected.formulas,
            table=expected.table,
            anchors=(),
        )

    if dispatch.ordered_request_id is None:
        raise ValueError("ordered dispatch must identify one ordered request")
    request_records = _unique_ordered_requests(manifest)
    request = request_records.get(dispatch.ordered_request_id)
    request_expectations = {
        item.request_id: item for item in expectations.ordered_requests
    }
    if len(request_expectations) != len(expectations.ordered_requests):
        raise ValueError("ordered scorer expectation ids must be unique")
    expected = request_expectations.get(dispatch.ordered_request_id)
    if request is None or expected is None:
        raise ValueError("ordered dispatch references an unknown ordered request")
    if (
        dispatch.fixture_ids != request.fixture_ids
        or expected.fixture_ids != dispatch.fixture_ids
    ):
        raise ValueError("ordered dispatch fixture order differs from its request")
    source_fixtures = tuple(fixture_records.get(value) for value in dispatch.fixture_ids)
    if any(fixture is None for fixture in source_fixtures):
        raise ValueError("ordered dispatch references an unknown source fixture")
    languages = tuple(
        dict.fromkeys(
            language
            for fixture in source_fixtures
            if fixture is not None
            for language in fixture.languages
        )
    )
    return _ResolvedScoringTarget(
        target=request.id,
        profile="ordered_request",
        languages=languages,
        neutral_markdown=_rules_for_profile(neutral_rules, "ordered_request"),
        text=expected.text,
        precision_text=expected.precision_text,
        critical_slots=expected.critical_slots,
        formulas=expected.formulas,
        table=expected.table,
        anchors=expected.anchors,
    )


def _unique_fixtures(
    manifest: Phase1FixtureManifest,
) -> dict[str, FixtureRecord]:
    if type(manifest.fixtures) is not tuple or any(
        type(item) is not FixtureRecord for item in manifest.fixtures
    ):
        raise TypeError("manifest fixtures must contain exact FixtureRecord values")
    result = {item.id: item for item in manifest.fixtures}
    if len(result) != len(manifest.fixtures):
        raise ValueError("manifest fixture ids must be unique")
    return result


def _unique_fixture_expectations(
    values: tuple[FixtureScorerExpectations, ...],
) -> dict[str, FixtureScorerExpectations]:
    result = {item.fixture_id: item for item in values}
    if len(result) != len(values):
        raise ValueError("fixture scorer expectation ids must be unique")
    return result


def _unique_ordered_requests(
    manifest: Phase1FixtureManifest,
) -> dict[str, OrderedRequestRecord]:
    if type(manifest.ordered_requests) is not tuple or any(
        type(item) is not OrderedRequestRecord for item in manifest.ordered_requests
    ):
        raise TypeError(
            "manifest ordered_requests must contain exact OrderedRequestRecord values"
        )
    result = {item.id: item for item in manifest.ordered_requests}
    if len(result) != len(manifest.ordered_requests):
        raise ValueError("manifest ordered-request ids must be unique")
    return result


def _unique_neutral_rules(
    manifest: Phase1FixtureManifest,
) -> dict[str, tuple[str, ...]]:
    values = manifest.scoring_contract.neutral_markdown
    if type(values) is not tuple or any(
        type(item) is not NeutralMarkdownRules for item in values
    ):
        raise TypeError("manifest neutral Markdown rules must be exact records")
    result = {item.profile: item.rules for item in values}
    if len(result) != len(values):
        raise ValueError("manifest neutral Markdown profiles must be unique")
    return result


def _rules_for_profile(
    values: dict[str, tuple[str, ...]],
    profile: str,
) -> tuple[str, ...]:
    rules = values.get(profile)
    if rules is None:
        raise ValueError(f"manifest has no neutral Markdown rules for {profile!r}")
    return rules


def _score_formula_view(
    expected: tuple[ExpectedFormula, ...],
    recognized: str,
) -> FormulaScore | None:
    if expected:
        return score_formula_signatures(expected, recognized)
    if recognized:
        raise ValueError("recognized Markdown contains an undeclared formula channel")
    return None


def _score_table_view(
    expected: ExpectedMarkdownTable | None,
    recognized: str | None,
) -> TableScore | None:
    if expected is None:
        if recognized is not None:
            raise ValueError("recognized Markdown contains an undeclared table channel")
        return None
    if recognized is None:
        return None
    return score_table_cells(expected, recognized)
