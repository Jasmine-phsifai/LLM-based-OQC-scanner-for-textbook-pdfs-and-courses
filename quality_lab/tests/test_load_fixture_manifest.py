from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from quality_lab.calculate_language_token_metrics import (
    LANGUAGE_TOKEN_KIND_BY_TAG,
)
from quality_lab.load_fixture_manifest import (
    DEFAULT_PHASE1_MANIFEST_PATH,
    FROZEN_PHASE1_MANIFEST_SHA256,
    ManifestValidationError,
    load_fixture_manifest,
)
from quality_lab.tokenize_content_units import tokenize_content_units


def _manifest_document() -> dict[str, object]:
    return json.loads(DEFAULT_PHASE1_MANIFEST_PATH.read_text(encoding="utf-8"))


def _load_modified_manifest(tmp_path: Path, document: dict[str, object]):
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return load_fixture_manifest(path, allow_unfrozen_for_testing=True)


def test_loads_frozen_five_class_manifest() -> None:
    manifest = load_fixture_manifest()

    assert manifest.schema_version == "ocrllm.phase1-fixture-manifest.v1"
    assert manifest.corpus_id == "phase1-image-quality.v1"
    assert manifest.max_corpus_bytes == 25 * 1024 * 1024
    assert manifest.scoring_contract.normalization_version == "content-units.v1"
    assert manifest.scoring_contract.tokenizer_version == "content-units.v1"
    assert manifest.scoring_contract.formula_dialect == "labeled-latex-restricted.v7"
    assert manifest.scoring_contract.table_dialect == "gfm-pipe-table-restricted.v1"
    assert manifest.scoring_contract.table_header_line_breaks == (
        "<br>",
        "<br/>",
        "<br />",
    )
    assert tuple(
        (rule.language, rule.token_kind)
        for rule in manifest.scoring_contract.language_token_kinds
    ) == tuple(LANGUAGE_TOKEN_KIND_BY_TAG.items())
    neutral_by_profile = {
        profile.profile: profile.rules
        for profile in manifest.scoring_contract.neutral_markdown
    }
    assert "table_delimiters" in neutral_by_profile["table"]
    assert "formula_delimiters" not in neutral_by_profile["table"]
    assert "formula_delimiters" in neutral_by_profile["formula_board"]
    assert "table_delimiters" not in neutral_by_profile["formula_board"]
    raw = DEFAULT_PHASE1_MANIFEST_PATH.read_bytes()
    assert manifest.raw_bytes == len(raw)
    assert manifest.raw_sha256 == hashlib.sha256(raw).hexdigest()
    assert manifest.raw_sha256 == FROZEN_PHASE1_MANIFEST_SHA256
    assert manifest.evidence_contract.model == "qwen3.7-plus-2026-05-26"
    assert manifest.evidence_contract.prompt_version == "board.v17"
    assert manifest.evidence_contract.draft_candidates == 1
    assert manifest.evidence_contract.review_passes == 0
    assert (
        manifest.evidence_contract.standalone_sign_scout_model
        == "qwen3.7-plus-2026-05-26"
    )
    assert manifest.evidence_contract.standalone_sign_scout_count == 3
    assert manifest.evidence_contract.standalone_sign_scout_enable_thinking is True
    assert manifest.evidence_contract.enable_thinking is True
    assert manifest.evidence_contract.vl_high_resolution_images is True
    assert [fixture.fixture_class for fixture in manifest.fixtures] == [
        "printed_slide",
        "degraded_printed_slide",
        "handwriting",
        "formula_board",
        "table",
    ]
    assert len(manifest.artifacts) == 20
    assert {license.spdx for license in manifest.licenses} == {
        "LicenseRef-OCRLLM-Repo-Owned-Test-Data",
        "CC0-1.0",
        "OFL-1.1",
    }


def test_manifest_contains_every_frozen_quality_count() -> None:
    manifest = load_fixture_manifest()
    by_class = {fixture.fixture_class: fixture for fixture in manifest.fixtures}

    assert len(by_class["printed_slide"].content_units) == 51
    assert len(by_class["printed_slide"].critical_slots) == 9
    assert by_class["degraded_printed_slide"].content_units == by_class[
        "printed_slide"
    ].content_units
    assert len(by_class["handwriting"].content_units) == 30
    assert len(by_class["handwriting"].optional_content_units) == 18
    assert len(by_class["handwriting"].critical_slots) == 10
    assert len(by_class["formula_board"].formulas) == 12
    table = by_class["table"].table
    assert table is not None
    assert (table.row_count, table.column_count) == (5, 6)
    assert len(table.headers) == 6
    assert len(table.cells) == 30
    assert sum(cell.column > 0 for cell in table.cells) == 25
    assert sum(
        cell.critical
        and cell.column > 0
        and any(any(character.isdigit() for character in form) for form in cell.accepted)
        for cell in table.cells
    ) == 20


def test_handwriting_separates_required_and_optional_source_occurrences() -> None:
    manifest = load_fixture_manifest()
    handwriting = next(
        fixture for fixture in manifest.fixtures if fixture.fixture_class == "handwriting"
    )
    # Required content controls recall; faint source labels are precision truth
    # but do not become false omissions when the provider cannot resolve them.
    tokens = tuple(
        token
        for unit in handwriting.content_units
        for token in tokenize_content_units(unit.text)
    )

    assert all(len(tokenize_content_units(unit.text)) == 1 for unit in handwriting.content_units)
    assert tuple(token.value for token in tokens) == (
        "MCS",
        "Plasmid",
        "Vector",
        "sticky",
        "End",
        "Blunt",
        "End",
        "foreign",
        "gene",
        "Enzymens",
        "Nuclease",
        "Cut",
        "Ligase",
        "join",
        "Transformation",
        "Validation",
        "selection",
        "screening",
        "I",
        "V",
        "3",
        "1",
        "Ratio",
        "+",
        "+",
        "R",
        "-",
        "DNA",
        "/",
        "Replasmid",
    )
    assert len(tokens) == 30
    optional_tokens = tuple(
        token.value
        for unit in handwriting.optional_content_units
        for token in tokenize_content_units(unit.text)
    )
    assert optional_tokens == (
        "AG",
        "R",
        "amp",
        "RG",
        "RG",
        "OR",
        "ATCG",
        "TAGC",
        "ACGT",
        "TGCA",
        "TA",
        "TA",
        "5",
        "5",
        "5",
        "3",
        "3",
        "3",
    )


def test_manifest_preserves_symbols_and_formula_dialect_truth() -> None:
    manifest = load_fixture_manifest()
    by_class = {fixture.fixture_class: fixture for fixture in manifest.fixtures}
    slide_text = {unit.text for unit in by_class["printed_slide"].content_units}
    visible_formulas = {
        formula.label: formula.visible_source
        for formula in by_class["formula_board"].formulas
    }
    formulas = {
        formula.label: formula.accepted_latex[0]
        for formula in by_class["formula_board"].formulas
    }

    assert "保留变量、符号与下标" in slide_text
    assert "TARGET RECALL: ≥ 95%" in slide_text
    assert visible_formulas["F02"] == "x₁ − 3x₂ ≤ −4"
    assert formulas["F05"] == r"P(A \mid B) = 0.625"
    assert formulas["F06"] == r"\det(M) = 3 \times 8 - 2 \times 5 = 14"
    assert formulas["F08"] == "f'(x) = 6x - 5"
    assert formulas["F09"] == r"\lVert u \rVert_{2} = \sqrt{25} = 5"
    assert formulas["F12"] == r"R_{n} = n(n + 1) / 2"


def test_manifest_freezes_five_singles_then_ordered_pair() -> None:
    manifest = load_fixture_manifest()

    assert tuple(dispatch.sequence for dispatch in manifest.live_dispatch_order) == tuple(
        range(6)
    )
    assert tuple(dispatch.kind for dispatch in manifest.live_dispatch_order) == (
        "single",
        "single",
        "single",
        "single",
        "single",
        "ordered",
    )
    assert manifest.live_dispatch_order[-1].fixture_ids == (
        "bilingual-printed-slide",
        "formula-integrity-board",
    )


def test_rejects_unknown_keys_at_every_object_boundary(tmp_path: Path) -> None:
    document = _manifest_document()
    evidence = document["evidence_contract"]
    assert isinstance(evidence, dict)
    evidence["retry_count"] = 1

    with pytest.raises(ManifestValidationError, match="unknown=.*retry_count"):
        _load_modified_manifest(tmp_path, document)


def test_rejects_duplicate_json_keys_before_schema_validation(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text('{"schema_version": "a", "schema_version": "b"}', encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="duplicate JSON key"):
        load_fixture_manifest(path)


def test_default_load_rejects_semantically_allowed_critical_slot_removal(
    tmp_path: Path,
) -> None:
    document = _manifest_document()
    fixtures = document["fixtures"]
    assert isinstance(fixtures, list) and isinstance(fixtures[2], dict)
    critical_slots = fixtures[2]["critical_slots"]
    assert isinstance(critical_slots, list) and len(critical_slots) == 10
    critical_slots.pop()
    path = tmp_path / "weakened-manifest.json"
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ManifestValidationError, match="raw SHA-256"):
        load_fixture_manifest(path)

    semantic_result = load_fixture_manifest(
        path,
        allow_unfrozen_for_testing=True,
    )
    weakened_handwriting = next(
        fixture
        for fixture in semantic_result.fixtures
        if fixture.fixture_class == "handwriting"
    )
    assert len(weakened_handwriting.critical_slots) == 9


def test_test_only_unfrozen_switch_requires_an_exact_boolean() -> None:
    with pytest.raises(TypeError, match="exact boolean"):
        load_fixture_manifest(
            allow_unfrozen_for_testing=1,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../fixture.png",
        "/tmp/fixture.png",
        "C:/fixture.png",
        "tests/fixtures/../fixture.png",
        "tests/fixtures/./fixture.png",
        "tests//fixtures/fixture.png",
        r"tests\fixtures\fixture.png",
    ],
)
def test_rejects_absolute_traversing_or_non_posix_artifact_paths(
    tmp_path: Path, unsafe_path: str
) -> None:
    document = _manifest_document()
    artifacts = document["artifacts"]
    assert isinstance(artifacts, list) and isinstance(artifacts[0], dict)
    artifacts[0]["path"] = unsafe_path

    with pytest.raises(ManifestValidationError, match="path"):
        _load_modified_manifest(tmp_path, document)


def test_rejects_non_pinned_evidence_contract(tmp_path: Path) -> None:
    document = _manifest_document()
    evidence = document["evidence_contract"]
    assert isinstance(evidence, dict)
    evidence["model"] = "qwen3.7-plus"

    with pytest.raises(ManifestValidationError, match="pinned Phase 1 request"):
        _load_modified_manifest(tmp_path, document)


def test_rejects_scoring_profile_or_generator_truth_drift(tmp_path: Path) -> None:
    scoring_drift = _manifest_document()
    scoring_contract = scoring_drift["scoring_contract"]
    assert isinstance(scoring_contract, dict)
    neutral = scoring_contract["neutral_markdown"]
    assert isinstance(neutral, dict) and isinstance(neutral["formula_board"], list)
    neutral["formula_board"].append("table_delimiters")
    with pytest.raises(ManifestValidationError, match="frozen Phase 1 scorer dialect"):
        _load_modified_manifest(tmp_path, scoring_drift)

    truth_drift = _manifest_document()
    fixtures = truth_drift["fixtures"]
    assert isinstance(fixtures, list) and isinstance(fixtures[0], dict)
    content = fixtures[0]["content_units"]
    assert isinstance(content, list) and isinstance(content[0], dict)
    content[0]["text"] = "DIFFERENT TITLE"
    degraded_content = fixtures[1]["content_units"]
    assert isinstance(degraded_content, list) and isinstance(degraded_content[0], dict)
    degraded_content[0]["text"] = "DIFFERENT TITLE"
    with pytest.raises(ManifestValidationError, match="deterministic generator"):
        _load_modified_manifest(tmp_path, truth_drift)


def test_rejects_language_token_mapping_drift_from_runtime(tmp_path: Path) -> None:
    mutations = (
        (
            "runtime mapping",
            lambda mapping: mapping.__setitem__("en-US", "han"),
        ),
        (
            "missing=.*zh-CN",
            lambda mapping: mapping.pop("zh-CN"),
        ),
        (
            "unknown=.*fr-FR",
            lambda mapping: mapping.__setitem__("fr-FR", "word"),
        ),
    )
    for message, mutate in mutations:
        document = _manifest_document()
        scoring_contract = document["scoring_contract"]
        assert isinstance(scoring_contract, dict)
        language_token_kinds = scoring_contract["language_token_kinds"]
        assert isinstance(language_token_kinds, dict)
        mutate(language_token_kinds)

        with pytest.raises(ManifestValidationError, match=message):
            _load_modified_manifest(tmp_path, document)


def test_rejects_invalid_ids_hashes_languages_and_redistribution(
    tmp_path: Path,
) -> None:
    mutations = (
        (
            "restricted lowercase id",
            lambda doc: doc["artifacts"][0].__setitem__("id", "Bad_ID"),
        ),
        ("SHA-256", lambda doc: doc["artifacts"][0].__setitem__("sha256", "A" * 64)),
        ("BCP-47", lambda doc: doc["fixtures"][0].__setitem__("languages", ["en_US"])),
        (
            "redistribution",
            lambda doc: doc["artifacts"][0].__setitem__("redistribution", "unknown"),
        ),
    )
    for name, mutate in mutations:
        document = _manifest_document()
        mutate(document)
        with pytest.raises(ManifestValidationError, match=name):
            _load_modified_manifest(tmp_path, document)


def test_rejects_duplicate_and_missing_table_coordinates(tmp_path: Path) -> None:
    duplicate = _manifest_document()
    fixtures = duplicate["fixtures"]
    assert isinstance(fixtures, list) and isinstance(fixtures[-1], dict)
    table = fixtures[-1]["table"]
    assert isinstance(table, dict)
    cells = table["cells"]
    assert isinstance(cells, list) and isinstance(cells[-1], dict)
    cells[-1]["row"] = 0
    cells[-1]["column"] = 0
    with pytest.raises(ManifestValidationError, match="duplicate table-cell coordinate"):
        _load_modified_manifest(tmp_path, duplicate)

    missing = _manifest_document()
    fixtures = missing["fixtures"]
    assert isinstance(fixtures, list) and isinstance(fixtures[-1], dict)
    table = fixtures[-1]["table"]
    assert isinstance(table, dict) and isinstance(table["cells"], list)
    table["cells"].pop()
    with pytest.raises(ManifestValidationError, match="complete declared rectangle"):
        _load_modified_manifest(tmp_path, missing)


def test_rejects_noncritical_numeric_table_cell(tmp_path: Path) -> None:
    document = _manifest_document()
    fixtures = document["fixtures"]
    assert isinstance(fixtures, list) and isinstance(fixtures[-1], dict)
    table = fixtures[-1]["table"]
    assert isinstance(table, dict) and isinstance(table["cells"], list)
    numeric_cell = table["cells"][1]
    assert isinstance(numeric_cell, dict)
    numeric_cell["critical"] = False

    with pytest.raises(ManifestValidationError, match="must be critical"):
        _load_modified_manifest(tmp_path, document)


@pytest.mark.parametrize(
    ("fixture_index", "field", "remaining", "message"),
    [
        (0, "content_units", 1, "at least 50 units"),
        (2, "content_units", 29, "at least 30 required atomic units"),
        (3, "formulas", 9, "at least 10 labeled formulas"),
    ],
)
def test_rejects_below_minimum_fixture_counts(
    tmp_path: Path,
    fixture_index: int,
    field: str,
    remaining: int,
    message: str,
) -> None:
    document = _manifest_document()
    fixtures = document["fixtures"]
    assert isinstance(fixtures, list) and isinstance(fixtures[fixture_index], dict)
    values = fixtures[fixture_index][field]
    assert isinstance(values, list)
    del values[remaining:]

    with pytest.raises(ManifestValidationError, match=message):
        _load_modified_manifest(tmp_path, document)


def test_rejects_invalid_optional_source_truth(tmp_path: Path) -> None:
    non_handwriting = _manifest_document()
    fixtures = non_handwriting["fixtures"]
    assert isinstance(fixtures, list) and isinstance(fixtures[0], dict)
    fixtures[0]["optional_content_units"] = [
        {"id": "unexpected-optional", "text": "extra", "case_sensitive": True}
    ]
    with pytest.raises(ManifestValidationError, match="must not declare optional"):
        _load_modified_manifest(tmp_path, non_handwriting)

    too_few = _manifest_document()
    fixtures = too_few["fixtures"]
    assert isinstance(fixtures, list) and isinstance(fixtures[2], dict)
    optional = fixtures[2]["optional_content_units"]
    assert isinstance(optional, list)
    del optional[9:]
    with pytest.raises(ManifestValidationError, match="10 optional atomic units"):
        _load_modified_manifest(tmp_path, too_few)

    duplicate_id = _manifest_document()
    fixtures = duplicate_id["fixtures"]
    assert isinstance(fixtures, list) and isinstance(fixtures[2], dict)
    content = fixtures[2]["content_units"]
    optional = fixtures[2]["optional_content_units"]
    assert isinstance(content, list) and isinstance(content[0], dict)
    assert isinstance(optional, list) and isinstance(optional[0], dict)
    optional[0]["id"] = content[0]["id"]
    with pytest.raises(ManifestValidationError, match="ids must be disjoint"):
        _load_modified_manifest(tmp_path, duplicate_id)


def test_rejects_wrong_fixture_count_and_ordered_source_coordinates(tmp_path: Path) -> None:
    missing_fixture = _manifest_document()
    fixtures = missing_fixture["fixtures"]
    assert isinstance(fixtures, list)
    fixtures.pop()
    with pytest.raises(ManifestValidationError, match="exactly five"):
        _load_modified_manifest(tmp_path, missing_fixture)

    wrong_order = _manifest_document()
    requests = wrong_order["ordered_requests"]
    assert isinstance(requests, list) and isinstance(requests[0], dict)
    anchors = requests[0]["anchors"]
    assert isinstance(anchors, list) and isinstance(anchors[1], dict)
    anchors[1]["source_index"] = 0
    with pytest.raises(ManifestValidationError, match="exactly 0 then 1"):
        _load_modified_manifest(tmp_path, wrong_order)

    dispatch_drift = _manifest_document()
    dispatches = dispatch_drift["live_dispatch_order"]
    assert isinstance(dispatches, list) and isinstance(dispatches[0], dict)
    dispatches[0]["fixture_ids"] = ["handwritten-whiteboard"]
    with pytest.raises(ManifestValidationError, match="frozen fixture order"):
        _load_modified_manifest(tmp_path, dispatch_drift)
