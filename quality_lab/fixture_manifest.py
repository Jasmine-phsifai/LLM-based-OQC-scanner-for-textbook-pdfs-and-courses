"""Immutable records for the committed Phase 1 quality manifest."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvidenceContract:
    """One pinned provider/request contract for comparable live evidence."""

    source_type: str
    profile: str
    provider: str
    model: str
    prompt_version: str
    draft_candidates: int
    review_passes: int
    standalone_sign_scout_model: str
    standalone_sign_scout_count: int
    standalone_sign_scout_enable_thinking: bool
    enable_thinking: bool
    vl_high_resolution_images: bool
    output_language: str | None


@dataclass(frozen=True, slots=True)
class NeutralMarkdownRules:
    """The only structural Markdown ignored for one scoring profile."""

    profile: str
    rules: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LanguageTokenKindRule:
    """One exact language tag to scored token-kind assignment."""

    language: str
    token_kind: str


@dataclass(frozen=True, slots=True)
class ScoringContract:
    """Frozen normalization, token, and recognized-Markdown dialect versions."""

    normalization_version: str
    tokenizer_version: str
    formula_dialect: str
    table_dialect: str
    table_header_line_breaks: tuple[str, ...]
    language_token_kinds: tuple[LanguageTokenKindRule, ...]
    neutral_markdown: tuple[NeutralMarkdownRules, ...]


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    """One hash-bound local file used by the corpus or its audit trail."""

    id: str
    path: str
    sha256: str
    bytes: int
    role: str
    redistribution: str
    license_id: str | None
    media_type: str | None
    pixel_width: int | None
    pixel_height: int | None


@dataclass(frozen=True, slots=True)
class LicenseRecord:
    """Redistribution terms and immutable local evidence for one asset set."""

    id: str
    spdx: str
    redistribution: str
    license_artifact_id: str
    provenance_artifact_id: str | None


@dataclass(frozen=True, slots=True)
class ScoredContentUnit:
    """One predeclared visible unit before scorer-version tokenization."""

    id: str
    text: str
    case_sensitive: bool


@dataclass(frozen=True, slots=True)
class CriticalTextSlot:
    """One visible value whose accepted forms are frozen before a live run."""

    id: str
    accepted: tuple[str, ...]
    case_sensitive: bool


@dataclass(frozen=True, slots=True)
class FormulaExpectation:
    """One labeled formula and its predeclared exact dialect forms."""

    label: str
    visible_source: str
    accepted_latex: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TableHeaderExpectation:
    """One exact table header at a zero-based column coordinate."""

    column: int
    accepted: tuple[str, ...]
    case_sensitive: bool


@dataclass(frozen=True, slots=True)
class TableCellExpectation:
    """One exact table value at a zero-based row/column coordinate."""

    row: int
    column: int
    accepted: tuple[str, ...]
    case_sensitive: bool
    critical: bool


@dataclass(frozen=True, slots=True)
class TableExpectation:
    """A complete rectangular table expectation."""

    row_count: int
    column_count: int
    headers: tuple[TableHeaderExpectation, ...]
    cells: tuple[TableCellExpectation, ...]


@dataclass(frozen=True, slots=True)
class FixtureRecord:
    """One of the five independently gated Phase 1 fixture classes."""

    id: str
    fixture_class: str
    artifact_id: str
    languages: tuple[str, ...]
    source_kind: str
    source_artifact_ids: tuple[str, ...]
    content_units: tuple[ScoredContentUnit, ...]
    optional_content_units: tuple[ScoredContentUnit, ...]
    critical_slots: tuple[CriticalTextSlot, ...]
    formulas: tuple[FormulaExpectation, ...]
    table: TableExpectation | None


@dataclass(frozen=True, slots=True)
class OrderedAnchorExpectation:
    """One unique source-indexed anchor in a multi-image request."""

    id: str
    source_index: int
    accepted: tuple[str, ...]
    case_sensitive: bool


@dataclass(frozen=True, slots=True)
class OrderedRequestRecord:
    """One fixed two-image request and its ordered anchors."""

    id: str
    fixture_ids: tuple[str, ...]
    anchors: tuple[OrderedAnchorExpectation, ...]


@dataclass(frozen=True, slots=True)
class LiveDispatchRecord:
    """One request in the fixed full-corpus live dispatch sequence."""

    sequence: int
    kind: str
    fixture_ids: tuple[str, ...]
    ordered_request_id: str | None


@dataclass(frozen=True, slots=True)
class Phase1FixtureManifest:
    """The fully validated, immutable Phase 1 corpus contract."""

    schema_version: str
    corpus_id: str
    max_corpus_bytes: int
    raw_sha256: str
    raw_bytes: int
    evidence_contract: EvidenceContract
    scoring_contract: ScoringContract
    artifacts: tuple[ArtifactRecord, ...]
    licenses: tuple[LicenseRecord, ...]
    fixtures: tuple[FixtureRecord, ...]
    ordered_requests: tuple[OrderedRequestRecord, ...]
    live_dispatch_order: tuple[LiveDispatchRecord, ...]
