"""Load and strictly validate the committed Phase 1 fixture manifest."""

from __future__ import annotations

import json
import hashlib
import re
import unicodedata
from pathlib import Path, PurePosixPath
from typing import NoReturn

from tests.quality.build_scorer_expectations import build_scorer_expectations
from tests.quality.build_scoring_views import build_scoring_views
from tests.quality.calculate_language_token_metrics import (
    LANGUAGE_TOKEN_KIND_BY_TAG,
)
from tests.quality.calculate_token_metrics import TokenMetricCounts
from tests.quality.calculate_token_metrics_with_optional_content import (
    calculate_token_metrics_with_optional_content,
)
from tests.quality.fixture_manifest import (
    ArtifactRecord,
    CriticalTextSlot,
    EvidenceContract,
    FixtureRecord,
    FormulaExpectation,
    LanguageTokenKindRule,
    LicenseRecord,
    LiveDispatchRecord,
    NeutralMarkdownRules,
    OrderedAnchorExpectation,
    OrderedRequestRecord,
    Phase1FixtureManifest,
    ScoredContentUnit,
    ScoringContract,
    TableCellExpectation,
    TableExpectation,
    TableHeaderExpectation,
)
from tests.quality.generators.phase1_fixture_content import (
    CANONICAL_FORMULAS,
    FORMULA_ORDER_ANCHOR,
    FORMULA_TITLE,
    SLIDE_CARDS,
    SLIDE_ORDER_ANCHOR,
    SLIDE_SUBTITLE,
    SLIDE_TITLE,
    TABLE_HEADERS,
    TABLE_ROWS,
    TABLE_TITLE,
    VISIBLE_FORMULAS,
)
from tests.quality.normalize_content_units import NORMALIZATION_VERSION
from tests.quality.normalize_recognized_markdown_v6 import (
    normalize_recognized_markdown_v6,
)
from tests.quality.parse_formula_signature import parse_formula_signature
from tests.quality.score_critical_slots import score_critical_slots
from tests.quality.score_formula_signatures import FormulaScore, score_formula_signatures
from tests.quality.score_ordered_anchors import score_ordered_anchors
from tests.quality.score_table_cells import (
    NEUTRAL_TABLE_LINE_BREAKS,
    ExpectedMarkdownTable,
    score_table_cells,
)
from tests.quality.tokenize_content_units import (
    ContentToken,
    TOKENIZER_VERSION,
    tokenize_content_units,
)


DEFAULT_PHASE1_MANIFEST_PATH = (
    Path(__file__).parents[1] / "fixtures" / "phase1" / "manifest.json"
)
FROZEN_PHASE1_MANIFEST_SHA256 = (
    "78df07bb720ab9a68b828c445ba5072ab1a0597e704a0ca48514bec8c26325f6"
)

_SCHEMA_VERSION = "ocrllm.phase1-fixture-manifest.v1"
_CORPUS_ID = "phase1-image-quality.v1"
_MAX_CORPUS_BYTES = 25 * 1024 * 1024
_MAX_MANIFEST_BYTES = 1024 * 1024
_ID = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_FORMULA_LABEL = re.compile(r"^F(?:0[1-9]|[1-9][0-9])$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_LANGUAGE_SUBTAG = re.compile(r"^[A-Za-z0-9]{1,8}$")

_FIXTURE_CLASSES = frozenset(
    {
        "printed_slide",
        "degraded_printed_slide",
        "handwriting",
        "formula_board",
        "table",
    }
)
_ARTIFACT_ROLES = frozenset(
    {"fixture-image", "generator-source", "generator-input", "provenance", "license"}
)
_REDISTRIBUTION_VALUES = frozenset(
    {"allowed", "allowed_unmodified_with_license", "evidence_copy"}
)
_LICENSE_SPREAD = {
    "repo-owned-test-data": (
        "LicenseRef-OCRLLM-Repo-Owned-Test-Data",
        "allowed",
    ),
    "cc0-whiteboard": ("CC0-1.0", "allowed"),
    "noto-sans-cjk-sc": ("OFL-1.1", "allowed_unmodified_with_license"),
}
_PINNED_EVIDENCE_CONTRACT = {
    "source_type": "image",
    "profile": "board",
    "provider": "dashscope",
    "model": "qwen3.7-plus-2026-05-26",
    "prompt_version": "board.v17",
    "draft_candidates": 1,
    "review_passes": 0,
    "standalone_sign_scout_model": "qwen3.7-plus-2026-05-26",
    "standalone_sign_scout_count": 3,
    "standalone_sign_scout_enable_thinking": True,
    "enable_thinking": True,
    "vl_high_resolution_images": True,
    "output_language": None,
}
_PINNED_SCORING_CONTRACT = {
    "normalization_version": NORMALIZATION_VERSION,
    "tokenizer_version": TOKENIZER_VERSION,
    "formula_dialect": "labeled-latex-restricted.v7",
    "table_dialect": "gfm-pipe-table-restricted.v1",
    "table_header_line_breaks": NEUTRAL_TABLE_LINE_BREAKS,
    "language_token_kinds": dict(LANGUAGE_TOKEN_KIND_BY_TAG),
    "neutral_markdown": {
        "printed_slide": (
            "headings",
            "unordered_list_markers",
            "ordered_list_markers",
            "emphasis",
        ),
        "degraded_printed_slide": (
            "headings",
            "unordered_list_markers",
            "ordered_list_markers",
            "emphasis",
        ),
        "handwriting": (
            "headings",
            "unordered_list_markers",
            "ordered_list_markers",
            "emphasis",
        ),
        "formula_board": (
            "headings",
            "unordered_list_markers",
            "ordered_list_markers",
            "emphasis",
            "formula_delimiters",
        ),
        "table": (
            "headings",
            "unordered_list_markers",
            "ordered_list_markers",
            "emphasis",
            "table_delimiters",
        ),
        "ordered_request": (
            "headings",
            "unordered_list_markers",
            "ordered_list_markers",
            "emphasis",
            "formula_delimiters",
        ),
    },
}


class ManifestValidationError(ValueError):
    """The committed corpus manifest is malformed or internally inconsistent."""


def load_fixture_manifest(
    path: str | Path = DEFAULT_PHASE1_MANIFEST_PATH,
    *,
    allow_unfrozen_for_testing: bool = False,
) -> Phase1FixtureManifest:
    """Return the byte-frozen manifest or explicitly validate a test mutation."""

    if type(allow_unfrozen_for_testing) is not bool:
        raise TypeError("allow_unfrozen_for_testing must be an exact boolean")

    manifest_path = Path(path)
    document, raw_sha256, raw_bytes = _load_json_object(manifest_path)
    if (
        not allow_unfrozen_for_testing
        and raw_sha256 != FROZEN_PHASE1_MANIFEST_SHA256
    ):
        _invalid("manifest raw SHA-256 differs from the frozen Phase 1 bytes")
    _require_keys(
        document,
        {
            "schema_version",
            "corpus_id",
            "max_corpus_bytes",
            "evidence_contract",
            "scoring_contract",
            "artifacts",
            "licenses",
            "fixtures",
            "ordered_requests",
            "live_dispatch_order",
        },
        "manifest",
    )
    schema_version = _require_text(document["schema_version"], "schema_version")
    corpus_id = _require_text(document["corpus_id"], "corpus_id")
    max_corpus_bytes = _require_integer(
        document["max_corpus_bytes"], "max_corpus_bytes", minimum=1
    )
    if schema_version != _SCHEMA_VERSION:
        _invalid("schema_version is not the frozen Phase 1 version")
    if corpus_id != _CORPUS_ID:
        _invalid("corpus_id is not the frozen Phase 1 corpus")
    if max_corpus_bytes != _MAX_CORPUS_BYTES:
        _invalid("max_corpus_bytes must be exactly 25 MiB")

    evidence_contract = _parse_evidence_contract(document["evidence_contract"])
    scoring_contract = _parse_scoring_contract(document["scoring_contract"])
    artifacts = _parse_artifacts(document["artifacts"])
    licenses = _parse_licenses(document["licenses"])
    fixtures = _parse_fixtures(document["fixtures"])
    ordered_requests = _parse_ordered_requests(document["ordered_requests"])
    live_dispatch_order = _parse_live_dispatch_order(document["live_dispatch_order"])
    manifest = Phase1FixtureManifest(
        schema_version=schema_version,
        corpus_id=corpus_id,
        max_corpus_bytes=max_corpus_bytes,
        raw_sha256=raw_sha256,
        raw_bytes=raw_bytes,
        evidence_contract=evidence_contract,
        scoring_contract=scoring_contract,
        artifacts=artifacts,
        licenses=licenses,
        fixtures=fixtures,
        ordered_requests=ordered_requests,
        live_dispatch_order=live_dispatch_order,
    )
    _validate_references(manifest)
    _validate_five_class_contract(manifest)
    _validate_generator_truth(manifest)
    _validate_ordered_requests(manifest)
    _validate_live_dispatch_order(manifest)
    _validate_scorer_compatibility(manifest)
    return manifest


def _load_json_object(path: Path) -> tuple[dict[str, object], str, int]:
    if path.is_symlink():
        _invalid("manifest path must not be a symlink")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ManifestValidationError("manifest could not be opened") from exc
    if size <= 0 or size > _MAX_MANIFEST_BYTES:
        _invalid("manifest size is outside the allowed range")
    try:
        raw = path.read_bytes()
        source = raw.decode("utf-8")
        document = json.loads(
            source,
            object_pairs_hook=_reject_duplicate_object_keys,
            parse_constant=_reject_nonfinite_json_constant,
        )
    except ManifestValidationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestValidationError("manifest is not strict UTF-8 JSON") from exc
    return _require_object(document, "manifest"), hashlib.sha256(raw).hexdigest(), len(raw)


def _reject_duplicate_object_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _invalid(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite_json_constant(value: str) -> NoReturn:
    _invalid(f"non-finite JSON number is forbidden: {value}")


def _parse_evidence_contract(value: object) -> EvidenceContract:
    document = _require_object(value, "evidence_contract")
    _require_keys(document, set(_PINNED_EVIDENCE_CONTRACT), "evidence_contract")
    if document != _PINNED_EVIDENCE_CONTRACT:
        _invalid("evidence_contract differs from the pinned Phase 1 request")
    return EvidenceContract(**document)  # type: ignore[arg-type]


def _parse_scoring_contract(value: object) -> ScoringContract:
    document = _require_object(value, "scoring_contract")
    _require_keys(document, set(_PINNED_SCORING_CONTRACT), "scoring_contract")
    normalized = {
        "normalization_version": _require_text(
            document["normalization_version"],
            "scoring_contract.normalization_version",
        ),
        "tokenizer_version": _require_text(
            document["tokenizer_version"], "scoring_contract.tokenizer_version"
        ),
        "formula_dialect": _require_text(
            document["formula_dialect"], "scoring_contract.formula_dialect"
        ),
        "table_dialect": _require_text(
            document["table_dialect"], "scoring_contract.table_dialect"
        ),
        "table_header_line_breaks": tuple(
            _require_text(
                item,
                f"scoring_contract.table_header_line_breaks[{index}]",
            )
            for index, item in enumerate(
                _require_list(
                    document["table_header_line_breaks"],
                    "scoring_contract.table_header_line_breaks",
                )
            )
        ),
        "language_token_kinds": _parse_language_token_kinds(
            document["language_token_kinds"]
        ),
        "neutral_markdown": _parse_neutral_markdown(document["neutral_markdown"]),
    }
    if normalized != _PINNED_SCORING_CONTRACT:
        _invalid("scoring_contract differs from the frozen Phase 1 scorer dialect")
    try:
        for profile, rules in normalized["neutral_markdown"].items():
            probe = "# **manifest dialect probe**"
            if profile in {"formula_board", "ordered_request"}:
                probe += "\nF01: $a_{1} = 2$"
            elif profile == "table":
                probe += "\n| A | B |\n| --- | --- |\n| 1 | 2 |"
            build_scoring_views(
                normalize_recognized_markdown_v6(probe),
                neutral_markdown=rules,
            )
    except (TypeError, ValueError) as exc:
        raise ManifestValidationError(
            "scoring_contract is not accepted by the current scoring-view builder"
        ) from exc
    return ScoringContract(
        normalization_version=normalized["normalization_version"],
        tokenizer_version=normalized["tokenizer_version"],
        formula_dialect=normalized["formula_dialect"],
        table_dialect=normalized["table_dialect"],
        table_header_line_breaks=normalized["table_header_line_breaks"],
        language_token_kinds=tuple(
            LanguageTokenKindRule(language=language, token_kind=token_kind)
            for language, token_kind in normalized["language_token_kinds"].items()
        ),
        neutral_markdown=tuple(
            NeutralMarkdownRules(profile=profile, rules=rules)
            for profile, rules in normalized["neutral_markdown"].items()
        ),
    )


def _parse_language_token_kinds(value: object) -> dict[str, str]:
    context = "scoring_contract.language_token_kinds"
    document = _require_object(value, context)
    expected_languages = set(LANGUAGE_TOKEN_KIND_BY_TAG)
    _require_keys(document, expected_languages, context)
    parsed = {
        language: _require_text(document[language], f"{context}.{language}")
        for language in LANGUAGE_TOKEN_KIND_BY_TAG
    }
    if parsed != dict(LANGUAGE_TOKEN_KIND_BY_TAG):
        _invalid(
            "scoring_contract.language_token_kinds differs from the runtime mapping"
        )
    return parsed


def _parse_neutral_markdown(value: object) -> dict[str, tuple[str, ...]]:
    document = _require_object(value, "scoring_contract.neutral_markdown")
    expected_profiles = set(_PINNED_SCORING_CONTRACT["neutral_markdown"])
    _require_keys(document, expected_profiles, "scoring_contract.neutral_markdown")
    return {
        profile: tuple(
            _require_text(
                item,
                f"scoring_contract.neutral_markdown.{profile}[{index}]",
            )
            for index, item in enumerate(
                _require_list(
                    document[profile],
                    f"scoring_contract.neutral_markdown.{profile}",
                )
            )
        )
        for profile in _PINNED_SCORING_CONTRACT["neutral_markdown"]
    }


def _parse_artifacts(value: object) -> tuple[ArtifactRecord, ...]:
    documents = _require_list(value, "artifacts")
    if not documents:
        _invalid("artifacts must not be empty")
    artifacts: list[ArtifactRecord] = []
    ids: set[str] = set()
    paths: set[str] = set()
    for index, value in enumerate(documents):
        context = f"artifacts[{index}]"
        document = _require_object(value, context)
        _require_keys(
            document,
            {
                "id",
                "path",
                "sha256",
                "bytes",
                "role",
                "redistribution",
                "license_id",
                "media_type",
                "pixel_width",
                "pixel_height",
            },
            context,
        )
        artifact_id = _require_id(document["id"], f"{context}.id")
        path = _require_relative_path(document["path"], f"{context}.path")
        sha256 = _require_text(document["sha256"], f"{context}.sha256")
        byte_count = _require_integer(document["bytes"], f"{context}.bytes", minimum=1)
        role = _require_text(document["role"], f"{context}.role")
        redistribution = _require_text(
            document["redistribution"], f"{context}.redistribution"
        )
        license_id = _require_optional_id(
            document["license_id"], f"{context}.license_id"
        )
        media_type = _require_optional_text(
            document["media_type"], f"{context}.media_type"
        )
        width = _require_optional_integer(
            document["pixel_width"], f"{context}.pixel_width", minimum=1
        )
        height = _require_optional_integer(
            document["pixel_height"], f"{context}.pixel_height", minimum=1
        )
        if artifact_id in ids:
            _invalid(f"duplicate artifact id: {artifact_id}")
        if path in paths:
            _invalid(f"duplicate artifact path: {path}")
        if _SHA256.fullmatch(sha256) is None:
            _invalid(f"{context}.sha256 must be lowercase SHA-256")
        if role not in _ARTIFACT_ROLES:
            _invalid(f"unsupported artifact role: {role}")
        if redistribution not in _REDISTRIBUTION_VALUES:
            _invalid(f"unsupported redistribution status: {redistribution}")
        if role == "fixture-image":
            if license_id is None:
                _invalid(f"{context} fixture image must name a license")
            if media_type not in {"image/png", "image/jpeg"}:
                _invalid(f"{context} fixture image has an unsupported media type")
            if width is None or height is None:
                _invalid(f"{context} fixture image must declare dimensions")
        elif media_type is not None or width is not None or height is not None:
            _invalid(f"{context} non-image metadata must be null")
        if role in {"generator-source", "generator-input"} and license_id is None:
            _invalid(f"{context} generator artifact must name a license")
        if role in {"provenance", "license"} and license_id is not None:
            _invalid(f"{context} audit evidence must not self-claim an asset license")
        artifacts.append(
            ArtifactRecord(
                id=artifact_id,
                path=path,
                sha256=sha256,
                bytes=byte_count,
                role=role,
                redistribution=redistribution,
                license_id=license_id,
                media_type=media_type,
                pixel_width=width,
                pixel_height=height,
            )
        )
        ids.add(artifact_id)
        paths.add(path)
    return tuple(artifacts)


def _parse_licenses(value: object) -> tuple[LicenseRecord, ...]:
    documents = _require_list(value, "licenses")
    if len(documents) != len(_LICENSE_SPREAD):
        _invalid("licenses must contain the three frozen Phase 1 asset licenses")
    records: list[LicenseRecord] = []
    ids: set[str] = set()
    for index, value in enumerate(documents):
        context = f"licenses[{index}]"
        document = _require_object(value, context)
        _require_keys(
            document,
            {
                "id",
                "spdx",
                "redistribution",
                "license_artifact_id",
                "provenance_artifact_id",
            },
            context,
        )
        license_id = _require_id(document["id"], f"{context}.id")
        spdx = _require_text(document["spdx"], f"{context}.spdx")
        redistribution = _require_text(
            document["redistribution"], f"{context}.redistribution"
        )
        license_artifact_id = _require_id(
            document["license_artifact_id"], f"{context}.license_artifact_id"
        )
        provenance_artifact_id = _require_optional_id(
            document["provenance_artifact_id"], f"{context}.provenance_artifact_id"
        )
        if license_id in ids:
            _invalid(f"duplicate license id: {license_id}")
        expected = _LICENSE_SPREAD.get(license_id)
        if expected is None or (spdx, redistribution) != expected:
            _invalid(f"license {license_id!r} differs from the frozen terms")
        records.append(
            LicenseRecord(
                id=license_id,
                spdx=spdx,
                redistribution=redistribution,
                license_artifact_id=license_artifact_id,
                provenance_artifact_id=provenance_artifact_id,
            )
        )
        ids.add(license_id)
    if ids != set(_LICENSE_SPREAD):
        _invalid("license ids differ from the frozen Phase 1 license set")
    return tuple(records)


def _parse_fixtures(value: object) -> tuple[FixtureRecord, ...]:
    documents = _require_list(value, "fixtures")
    if len(documents) != len(_FIXTURE_CLASSES):
        _invalid("fixtures must contain exactly five entries")
    fixtures: list[FixtureRecord] = []
    ids: set[str] = set()
    for index, value in enumerate(documents):
        context = f"fixtures[{index}]"
        document = _require_object(value, context)
        _require_keys(
            document,
            {
                "id",
                "fixture_class",
                "artifact_id",
                "languages",
                "source_kind",
                "source_artifact_ids",
                "content_units",
                "optional_content_units",
                "critical_slots",
                "formulas",
                "table",
            },
            context,
        )
        fixture_id = _require_id(document["id"], f"{context}.id")
        fixture_class = _require_text(
            document["fixture_class"], f"{context}.fixture_class"
        )
        artifact_id = _require_id(document["artifact_id"], f"{context}.artifact_id")
        languages = _parse_languages(document["languages"], f"{context}.languages")
        source_kind = _require_text(document["source_kind"], f"{context}.source_kind")
        source_artifact_ids = _parse_unique_ids(
            document["source_artifact_ids"], f"{context}.source_artifact_ids"
        )
        content_units = _parse_content_units(
            document["content_units"], f"{context}.content_units"
        )
        optional_content_units = _parse_content_units(
            document["optional_content_units"],
            f"{context}.optional_content_units",
        )
        critical_slots = _parse_critical_slots(
            document["critical_slots"], f"{context}.critical_slots"
        )
        formulas = _parse_formulas(document["formulas"], f"{context}.formulas")
        table = _parse_table(document["table"], f"{context}.table")
        if fixture_id in ids:
            _invalid(f"duplicate fixture id: {fixture_id}")
        if fixture_class not in _FIXTURE_CLASSES:
            _invalid(f"unknown Phase 1 fixture class: {fixture_class}")
        expected_source_kind = (
            "licensed_derivative" if fixture_class == "handwriting" else "deterministic_generator"
        )
        if source_kind != expected_source_kind:
            _invalid(f"{fixture_class} has the wrong source_kind")
        if not source_artifact_ids:
            _invalid(f"{context}.source_artifact_ids must not be empty")
        _validate_fixture_channels(
            fixture_class,
            content_units=content_units,
            optional_content_units=optional_content_units,
            critical_slots=critical_slots,
            formulas=formulas,
            table=table,
        )
        fixtures.append(
            FixtureRecord(
                id=fixture_id,
                fixture_class=fixture_class,
                artifact_id=artifact_id,
                languages=languages,
                source_kind=source_kind,
                source_artifact_ids=source_artifact_ids,
                content_units=content_units,
                optional_content_units=optional_content_units,
                critical_slots=critical_slots,
                formulas=formulas,
                table=table,
            )
        )
        ids.add(fixture_id)
    return tuple(fixtures)


def _parse_content_units(value: object, context: str) -> tuple[ScoredContentUnit, ...]:
    documents = _require_list(value, context)
    units: list[ScoredContentUnit] = []
    ids: set[str] = set()
    for index, value in enumerate(documents):
        unit_context = f"{context}[{index}]"
        document = _require_object(value, unit_context)
        _require_keys(document, {"id", "text", "case_sensitive"}, unit_context)
        unit_id = _require_id(document["id"], f"{unit_context}.id")
        text = _require_text(document["text"], f"{unit_context}.text")
        case_sensitive = _require_boolean(
            document["case_sensitive"], f"{unit_context}.case_sensitive"
        )
        if unit_id in ids:
            _invalid(f"duplicate content-unit id: {unit_id}")
        units.append(
            ScoredContentUnit(id=unit_id, text=text, case_sensitive=case_sensitive)
        )
        ids.add(unit_id)
    return tuple(units)


def _parse_critical_slots(value: object, context: str) -> tuple[CriticalTextSlot, ...]:
    documents = _require_list(value, context)
    slots: list[CriticalTextSlot] = []
    ids: set[str] = set()
    for index, value in enumerate(documents):
        slot_context = f"{context}[{index}]"
        document = _require_object(value, slot_context)
        _require_keys(document, {"id", "accepted", "case_sensitive"}, slot_context)
        slot_id = _require_id(document["id"], f"{slot_context}.id")
        accepted = _parse_nonempty_text_tuple(
            document["accepted"], f"{slot_context}.accepted"
        )
        case_sensitive = _require_boolean(
            document["case_sensitive"], f"{slot_context}.case_sensitive"
        )
        if slot_id in ids:
            _invalid(f"duplicate critical-slot id: {slot_id}")
        _reject_duplicate_normalized_forms(accepted, case_sensitive, slot_context)
        slots.append(
            CriticalTextSlot(
                id=slot_id,
                accepted=accepted,
                case_sensitive=case_sensitive,
            )
        )
        ids.add(slot_id)
    return tuple(slots)


def _parse_formulas(value: object, context: str) -> tuple[FormulaExpectation, ...]:
    documents = _require_list(value, context)
    formulas: list[FormulaExpectation] = []
    labels: set[str] = set()
    for index, value in enumerate(documents):
        formula_context = f"{context}[{index}]"
        document = _require_object(value, formula_context)
        _require_keys(
            document,
            {"label", "visible_source", "accepted_latex"},
            formula_context,
        )
        label = _require_text(document["label"], f"{formula_context}.label")
        visible_source = _require_text(
            document["visible_source"], f"{formula_context}.visible_source"
        )
        accepted = _parse_nonempty_text_tuple(
            document["accepted_latex"], f"{formula_context}.accepted_latex"
        )
        if _FORMULA_LABEL.fullmatch(label) is None:
            _invalid(f"{formula_context}.label is not a restricted formula label")
        if label in labels:
            _invalid(f"duplicate formula label: {label}")
        _reject_duplicate_normalized_forms(accepted, True, formula_context)
        try:
            visible_signature = parse_formula_signature(visible_source)
            accepted_signatures = tuple(parse_formula_signature(form) for form in accepted)
        except (TypeError, ValueError) as exc:
            raise ManifestValidationError(
                f"{formula_context} is outside the frozen formula dialect"
            ) from exc
        if visible_signature not in accepted_signatures:
            _invalid(f"{formula_context} visible and accepted formula signatures differ")
        formulas.append(
            FormulaExpectation(
                label=label,
                visible_source=visible_source,
                accepted_latex=accepted,
            )
        )
        labels.add(label)
    return tuple(formulas)


def _parse_table(value: object, context: str) -> TableExpectation | None:
    if value is None:
        return None
    document = _require_object(value, context)
    _require_keys(document, {"row_count", "column_count", "headers", "cells"}, context)
    row_count = _require_integer(document["row_count"], f"{context}.row_count", minimum=1)
    column_count = _require_integer(
        document["column_count"], f"{context}.column_count", minimum=1
    )
    header_documents = _require_list(document["headers"], f"{context}.headers")
    headers: list[TableHeaderExpectation] = []
    header_coordinates: set[int] = set()
    for index, value in enumerate(header_documents):
        header_context = f"{context}.headers[{index}]"
        header = _require_object(value, header_context)
        _require_keys(header, {"column", "accepted", "case_sensitive"}, header_context)
        column = _require_integer(header["column"], f"{header_context}.column", minimum=0)
        accepted = _parse_nonempty_text_tuple(
            header["accepted"], f"{header_context}.accepted"
        )
        case_sensitive = _require_boolean(
            header["case_sensitive"], f"{header_context}.case_sensitive"
        )
        if column in header_coordinates:
            _invalid(f"duplicate table-header coordinate: {column}")
        _reject_duplicate_normalized_forms(accepted, case_sensitive, header_context)
        headers.append(
            TableHeaderExpectation(
                column=column,
                accepted=accepted,
                case_sensitive=case_sensitive,
            )
        )
        header_coordinates.add(column)

    cell_documents = _require_list(document["cells"], f"{context}.cells")
    cells: list[TableCellExpectation] = []
    cell_coordinates: set[tuple[int, int]] = set()
    for index, value in enumerate(cell_documents):
        cell_context = f"{context}.cells[{index}]"
        cell = _require_object(value, cell_context)
        _require_keys(
            cell,
            {"row", "column", "accepted", "case_sensitive", "critical"},
            cell_context,
        )
        row = _require_integer(cell["row"], f"{cell_context}.row", minimum=0)
        column = _require_integer(cell["column"], f"{cell_context}.column", minimum=0)
        accepted = _parse_nonempty_text_tuple(cell["accepted"], f"{cell_context}.accepted")
        case_sensitive = _require_boolean(
            cell["case_sensitive"], f"{cell_context}.case_sensitive"
        )
        critical = _require_boolean(cell["critical"], f"{cell_context}.critical")
        coordinate = (row, column)
        if coordinate in cell_coordinates:
            _invalid(f"duplicate table-cell coordinate: {coordinate}")
        if any(_looks_critical_text(option) for option in accepted) and not critical:
            _invalid(f"numeric/signed table cell {coordinate} must be critical")
        _reject_duplicate_normalized_forms(accepted, case_sensitive, cell_context)
        cells.append(
            TableCellExpectation(
                row=row,
                column=column,
                accepted=accepted,
                case_sensitive=case_sensitive,
                critical=critical,
            )
        )
        cell_coordinates.add(coordinate)

    expected_headers = set(range(column_count))
    expected_cells = {
        (row, column) for row in range(row_count) for column in range(column_count)
    }
    if header_coordinates != expected_headers:
        _invalid("table headers must cover every declared column exactly once")
    if cell_coordinates != expected_cells:
        _invalid("table cells must cover the complete declared rectangle")
    expectation = TableExpectation(
        row_count=row_count,
        column_count=column_count,
        headers=tuple(sorted(headers, key=lambda header: header.column)),
        cells=tuple(sorted(cells, key=lambda cell: (cell.row, cell.column))),
    )
    return expectation


def _parse_ordered_requests(value: object) -> tuple[OrderedRequestRecord, ...]:
    documents = _require_list(value, "ordered_requests")
    if len(documents) != 1:
        _invalid("ordered_requests must contain exactly one two-image request")
    requests: list[OrderedRequestRecord] = []
    for index, value in enumerate(documents):
        context = f"ordered_requests[{index}]"
        document = _require_object(value, context)
        _require_keys(document, {"id", "fixture_ids", "anchors"}, context)
        request_id = _require_id(document["id"], f"{context}.id")
        fixture_ids = _parse_unique_ids(document["fixture_ids"], f"{context}.fixture_ids")
        anchor_documents = _require_list(document["anchors"], f"{context}.anchors")
        anchors: list[OrderedAnchorExpectation] = []
        anchor_ids: set[str] = set()
        for anchor_index, value in enumerate(anchor_documents):
            anchor_context = f"{context}.anchors[{anchor_index}]"
            anchor = _require_object(value, anchor_context)
            _require_keys(
                anchor,
                {"id", "source_index", "accepted", "case_sensitive"},
                anchor_context,
            )
            anchor_id = _require_id(anchor["id"], f"{anchor_context}.id")
            source_index = _require_integer(
                anchor["source_index"], f"{anchor_context}.source_index", minimum=0
            )
            accepted = _parse_nonempty_text_tuple(
                anchor["accepted"], f"{anchor_context}.accepted"
            )
            case_sensitive = _require_boolean(
                anchor["case_sensitive"], f"{anchor_context}.case_sensitive"
            )
            if anchor_id in anchor_ids:
                _invalid(f"duplicate ordered-anchor id: {anchor_id}")
            _reject_duplicate_normalized_forms(accepted, case_sensitive, anchor_context)
            anchors.append(
                OrderedAnchorExpectation(
                    id=anchor_id,
                    source_index=source_index,
                    accepted=accepted,
                    case_sensitive=case_sensitive,
                )
            )
            anchor_ids.add(anchor_id)
        requests.append(
            OrderedRequestRecord(
                id=request_id,
                fixture_ids=fixture_ids,
                anchors=tuple(anchors),
            )
        )
    return tuple(requests)


def _parse_live_dispatch_order(value: object) -> tuple[LiveDispatchRecord, ...]:
    documents = _require_list(value, "live_dispatch_order")
    if len(documents) != 6:
        _invalid("live_dispatch_order must contain five singles and one ordered request")
    dispatches: list[LiveDispatchRecord] = []
    for index, value in enumerate(documents):
        context = f"live_dispatch_order[{index}]"
        document = _require_object(value, context)
        _require_keys(
            document,
            {"sequence", "kind", "fixture_ids", "ordered_request_id"},
            context,
        )
        sequence = _require_integer(
            document["sequence"], f"{context}.sequence", minimum=0
        )
        kind = _require_text(document["kind"], f"{context}.kind")
        fixture_ids = _parse_unique_ids(
            document["fixture_ids"], f"{context}.fixture_ids"
        )
        ordered_request_id = _require_optional_id(
            document["ordered_request_id"], f"{context}.ordered_request_id"
        )
        if kind not in {"single", "ordered"}:
            _invalid(f"{context}.kind must be 'single' or 'ordered'")
        dispatches.append(
            LiveDispatchRecord(
                sequence=sequence,
                kind=kind,
                fixture_ids=fixture_ids,
                ordered_request_id=ordered_request_id,
            )
        )
    return tuple(dispatches)


def _validate_references(manifest: Phase1FixtureManifest) -> None:
    artifact_by_id = {artifact.id: artifact for artifact in manifest.artifacts}
    license_by_id = {license.id: license for license in manifest.licenses}
    fixture_ids = {fixture.id for fixture in manifest.fixtures}
    referenced_artifacts: set[str] = set()

    for license in manifest.licenses:
        license_artifact = artifact_by_id.get(license.license_artifact_id)
        if license_artifact is None or license_artifact.role != "license":
            _invalid(f"license {license.id!r} has no local license artifact")
        referenced_artifacts.add(license.license_artifact_id)
        if license.provenance_artifact_id is not None:
            provenance = artifact_by_id.get(license.provenance_artifact_id)
            if provenance is None or provenance.role != "provenance":
                _invalid(f"license {license.id!r} has invalid provenance evidence")
            referenced_artifacts.add(license.provenance_artifact_id)

    for artifact in manifest.artifacts:
        if artifact.license_id is not None:
            license = license_by_id.get(artifact.license_id)
            if license is None:
                _invalid(f"artifact {artifact.id!r} references an unknown license")
            if artifact.redistribution != license.redistribution:
                _invalid(f"artifact {artifact.id!r} redistribution conflicts with its license")

    for fixture in manifest.fixtures:
        artifact = artifact_by_id.get(fixture.artifact_id)
        if artifact is None or artifact.role != "fixture-image":
            _invalid(f"fixture {fixture.id!r} must reference one fixture image")
        referenced_artifacts.add(fixture.artifact_id)
        for artifact_id in fixture.source_artifact_ids:
            source = artifact_by_id.get(artifact_id)
            if source is None:
                _invalid(f"fixture {fixture.id!r} references an unknown source artifact")
            if source.role == "fixture-image":
                _invalid(f"fixture {fixture.id!r} uses an image as generator evidence")
            referenced_artifacts.add(artifact_id)
        source_roles = {
            artifact_by_id[artifact_id].role for artifact_id in fixture.source_artifact_ids
        }
        if (
            fixture.source_kind == "deterministic_generator"
            and "generator-source" not in source_roles
        ):
            _invalid(f"fixture {fixture.id!r} lacks deterministic generator evidence")
        if fixture.source_kind == "licensed_derivative" and not {
            "provenance",
            "license",
        }.issubset(source_roles):
            _invalid(f"fixture {fixture.id!r} lacks local provenance/license evidence")

    for request in manifest.ordered_requests:
        if any(fixture_id not in fixture_ids for fixture_id in request.fixture_ids):
            _invalid(f"ordered request {request.id!r} references an unknown fixture")

    orphaned = set(artifact_by_id) - referenced_artifacts
    if orphaned:
        _invalid(f"manifest contains unreferenced artifacts: {sorted(orphaned)!r}")


def _validate_five_class_contract(manifest: Phase1FixtureManifest) -> None:
    by_class = {fixture.fixture_class: fixture for fixture in manifest.fixtures}
    if set(by_class) != _FIXTURE_CLASSES:
        _invalid("fixtures must contain each frozen class exactly once")
    expected_languages = {
        "printed_slide": ("en-US", "zh-CN"),
        "degraded_printed_slide": ("en-US", "zh-CN"),
        "handwriting": ("en-US",),
        "formula_board": ("en-US", "zh-CN"),
        "table": ("en-US", "zh-CN"),
    }
    for fixture_class, fixture in by_class.items():
        if fixture.languages != expected_languages[fixture_class]:
            _invalid(f"{fixture_class} languages differ from the frozen corpus")

    clean = by_class["printed_slide"]
    degraded = by_class["degraded_printed_slide"]
    if (
        clean.content_units != degraded.content_units
        or clean.optional_content_units != degraded.optional_content_units
        or clean.critical_slots != degraded.critical_slots
    ):
        _invalid("the degraded slide must retain the clean slide ground truth")


def _validate_generator_truth(manifest: Phase1FixtureManifest) -> None:
    by_class = {fixture.fixture_class: fixture for fixture in manifest.fixtures}
    if any(
        fixture.optional_content_units
        for fixture in manifest.fixtures
        if fixture.fixture_class != "handwriting"
    ):
        _invalid("deterministic generator fixtures must not declare optional content")
    slide_truth = (SLIDE_TITLE, SLIDE_SUBTITLE, SLIDE_ORDER_ANCHOR) + tuple(
        line for card in SLIDE_CARDS for line in card
    )
    for fixture_class in ("printed_slide", "degraded_printed_slide"):
        actual = tuple(unit.text for unit in by_class[fixture_class].content_units)
        if actual != slide_truth:
            _invalid(f"{fixture_class} text differs from the deterministic generator")

    formula_fixture = by_class["formula_board"]
    if tuple(unit.text for unit in formula_fixture.content_units) != (
        FORMULA_TITLE,
        FORMULA_ORDER_ANCHOR,
    ):
        _invalid("formula-board residual text differs from the deterministic generator")
    if tuple(
        (formula.label, formula.visible_source) for formula in formula_fixture.formulas
    ) != VISIBLE_FORMULAS:
        _invalid("visible formulas differ from the deterministic generator")
    if tuple(
        (formula.label, formula.accepted_latex[0])
        for formula in formula_fixture.formulas
    ) != CANONICAL_FORMULAS:
        _invalid("canonical formulas differ from the deterministic generator")

    table_fixture = by_class["table"]
    if tuple(unit.text for unit in table_fixture.content_units) != (TABLE_TITLE,):
        _invalid("table residual text differs from the deterministic generator")
    if table_fixture.table is None:
        _invalid("table generator truth has no coordinate expectation")
    expected_headers = tuple(f"{english} {chinese}" for english, chinese in TABLE_HEADERS)
    actual_headers = tuple(header.accepted[0] for header in table_fixture.table.headers)
    actual_rows = tuple(
        tuple(
            next(
                cell.accepted[0]
                for cell in table_fixture.table.cells
                if (cell.row, cell.column) == (row, column)
            )
            for column in range(table_fixture.table.column_count)
        )
        for row in range(table_fixture.table.row_count)
    )
    if actual_headers != expected_headers or actual_rows != TABLE_ROWS:
        _invalid("table coordinates differ from the deterministic generator")


def _validate_fixture_channels(
    fixture_class: str,
    *,
    content_units: tuple[ScoredContentUnit, ...],
    optional_content_units: tuple[ScoredContentUnit, ...],
    critical_slots: tuple[CriticalTextSlot, ...],
    formulas: tuple[FormulaExpectation, ...],
    table: TableExpectation | None,
) -> None:
    required_ids = {unit.id for unit in content_units}
    optional_ids = {unit.id for unit in optional_content_units}
    if required_ids & optional_ids:
        _invalid("required and optional content-unit ids must be disjoint")
    tokenized_units = _tokenize_scored_content_units(content_units)
    optional_tokenized_units = _tokenize_scored_content_units(
        optional_content_units,
    )
    flattened_tokens = tuple(token for tokens in tokenized_units for token in tokens)
    optional_flattened_tokens = tuple(
        token for tokens in optional_tokenized_units for token in tokens
    )
    scored_token_count = len(flattened_tokens)

    if fixture_class != "handwriting" and optional_content_units:
        _invalid(f"{fixture_class} must not declare optional content units")

    if fixture_class in {"printed_slide", "degraded_printed_slide"}:
        if scored_token_count < 50 or len(critical_slots) < 8:
            _invalid(f"{fixture_class} requires at least 50 units and 8 critical slots")
    elif fixture_class == "handwriting":
        if (
            scored_token_count < 30
            or any(len(tokens) != 1 for tokens in tokenized_units)
            or len(optional_flattened_tokens) < 10
            or any(len(tokens) != 1 for tokens in optional_tokenized_units)
            or len(critical_slots) < 5
        ):
            _invalid(
                "handwriting requires at least 30 required atomic units, "
                "10 optional atomic units, and 5 critical slots"
            )
    elif fixture_class == "formula_board":
        if len(formulas) < 10:
            _invalid("formula_board requires at least 10 labeled formulas")
    elif fixture_class == "table":
        if table is None:
            _invalid("table fixture must declare a complete table")
        data_cell_count = table.row_count * (table.column_count - 1)
        critical_numeric_count = sum(
            cell.critical
            and cell.column > 0
            and any(any(character.isdigit() for character in value) for value in cell.accepted)
            for cell in table.cells
        )
        if data_cell_count < 20 or critical_numeric_count < 5:
            _invalid("table requires at least 20 data cells and 5 critical numeric cells")

    if fixture_class != "formula_board" and formulas:
        _invalid(f"{fixture_class} must not declare formula-channel expectations")
    if fixture_class != "table" and table is not None:
        _invalid(f"{fixture_class} must not declare table-channel expectations")
    if fixture_class == "table" and table is None:
        _invalid("table fixture must declare table-channel expectations")


def _tokenize_scored_content_units(
    content_units: tuple[ScoredContentUnit, ...],
) -> tuple[tuple[ContentToken, ...], ...]:
    tokenized_units: list[tuple[ContentToken, ...]] = []
    for unit in content_units:
        try:
            tokens = tokenize_content_units(unit.text)
        except (TypeError, ValueError) as exc:
            raise ManifestValidationError(
                f"content unit {unit.id!r} is outside the frozen token dialect"
            ) from exc
        if not tokens:
            _invalid(f"content unit {unit.id!r} has no scored token")
        tokenized_units.append(tokens)
    return tuple(tokenized_units)



def _validate_ordered_requests(manifest: Phase1FixtureManifest) -> None:
    fixture_by_id = {fixture.id: fixture for fixture in manifest.fixtures}
    request = manifest.ordered_requests[0]
    if len(request.fixture_ids) != 2:
        _invalid("the ordered request must contain exactly two distinct fixture ids")
    if len(request.anchors) != 2:
        _invalid("the ordered request must contain exactly one anchor per source")
    if tuple(anchor.source_index for anchor in request.anchors) != (0, 1):
        _invalid("ordered-anchor source indexes must be exactly 0 then 1")
    if tuple(
        fixture_by_id[fixture_id].fixture_class for fixture_id in request.fixture_ids
    ) != ("printed_slide", "formula_board"):
        _invalid("the ordered request must run the clean slide before the formula board")

def _validate_live_dispatch_order(manifest: Phase1FixtureManifest) -> None:
    dispatches = manifest.live_dispatch_order
    if tuple(dispatch.sequence for dispatch in dispatches) != tuple(range(6)):
        _invalid("live dispatch sequence must be contiguous from 0 through 5")
    singles = dispatches[:5]
    expected_single_ids = tuple(fixture.id for fixture in manifest.fixtures)
    if any(
        dispatch.kind != "single"
        or len(dispatch.fixture_ids) != 1
        or dispatch.ordered_request_id is not None
        for dispatch in singles
    ):
        _invalid("the first five live dispatches must be independent single fixtures")
    if tuple(dispatch.fixture_ids[0] for dispatch in singles) != expected_single_ids:
        _invalid("single-fixture live dispatch order must match the frozen fixture order")

    ordered = dispatches[5]
    request = manifest.ordered_requests[0]
    if (
        ordered.kind != "ordered"
        or ordered.fixture_ids != request.fixture_ids
        or ordered.ordered_request_id != request.id
    ):
        _invalid("the final live dispatch must be the frozen ordered two-image request")


def _validate_scorer_compatibility(manifest: Phase1FixtureManifest) -> None:
    try:
        expectations = build_scorer_expectations(manifest)
        fixtures_by_id = {fixture.id: fixture for fixture in manifest.fixtures}
        for expected in expectations.fixtures:
            fixture = fixtures_by_id[expected.fixture_id]
            recognized_text = " ".join(
                unit.text
                for unit in fixture.content_units + fixture.optional_content_units
            )
            text_score = calculate_token_metrics_with_optional_content(
                expected.text,
                expected.precision_text,
                tokenize_content_units(recognized_text),
            )
            if not _token_metrics_are_perfect(text_score):
                _invalid("content units are not a perfect frozen scorer fixture")

            if expected.critical_slots:
                critical_score = score_critical_slots(
                    expected.critical_slots,
                    recognized_text,
                )
                if not critical_score.passes:
                    _invalid(
                        "critical slots do not map exactly once onto declared fixture truth"
                    )

            if expected.formulas:
                perfect_markdown = "\n".join(
                    f"{formula.label}: ${formula.accepted_latex[0]}$"
                    for formula in expected.formulas
                )
                formula_score = score_formula_signatures(
                    expected.formulas,
                    perfect_markdown,
                )
                if not _formula_score_is_perfect(formula_score):
                    _invalid(
                        "formula expectations are not a perfect frozen scorer fixture"
                    )

            if expected.table is not None:
                _validate_perfect_table_forms(expected.table)

        for expected in expectations.ordered_requests:
            ordered_text = "\n".join(
                " ".join(
                    unit.text
                    for unit in (
                        fixtures_by_id[fixture_id].content_units
                        + fixtures_by_id[fixture_id].optional_content_units
                    )
                )
                for fixture_id in expected.fixture_ids
            )
            anchor_score = score_ordered_anchors(
                expected.anchors,
                ordered_text,
                actual_source_indices=tuple(range(len(expected.fixture_ids))),
                actual_image_count=len(expected.fixture_ids),
            )
            if not anchor_score.passes:
                _invalid("ordered anchors do not map exactly once in source order")
    except ManifestValidationError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ManifestValidationError(
            "manifest truth is incompatible with the frozen scorer types"
        ) from exc


def _token_metrics_are_perfect(score: TokenMetricCounts) -> bool:
    return bool(
        score.recall.numerator == score.recall.denominator
        and score.precision.numerator == score.precision.denominator
        and score.critical_accuracy.numerator == score.critical_accuracy.denominator
        and not score.unmatched_recognized_indexes
        and not score.unexpected_critical_indexes
    )


def _formula_score_is_perfect(score: FormulaScore) -> bool:
    return bool(
        score.signature_accuracy.numerator == score.signature_accuracy.denominator
        and score.atom_precision.numerator == score.atom_precision.denominator
        and score.critical_accuracy.numerator == score.critical_accuracy.denominator
        and not score.missing_labels
        and not score.unexpected_labels
        and not score.missing_atom_count
        and not score.unexpected_atom_count
    )


def _parse_languages(value: object, context: str) -> tuple[str, ...]:
    values = _require_list(value, context)
    if not values:
        _invalid(f"{context} must not be empty")
    result: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(values):
        language = _require_text(value, f"{context}[{index}]")
        subtags = language.split("-")
        first = subtags[0]
        ordinary = first.isalpha() and 2 <= len(first) <= 8
        private = first.casefold() in {"x", "i"} and len(subtags) > 1
        if not (ordinary or private) or any(
            _LANGUAGE_SUBTAG.fullmatch(subtag) is None for subtag in subtags
        ):
            _invalid(f"{context} contains an invalid BCP-47 language tag")
        folded = language.casefold()
        if folded in seen:
            _invalid(f"{context} contains duplicate language tags")
        result.append(language)
        seen.add(folded)
    return tuple(result)


def _parse_unique_ids(value: object, context: str) -> tuple[str, ...]:
    values = _require_list(value, context)
    result = tuple(_require_id(item, f"{context}[{index}]") for index, item in enumerate(values))
    if len(set(result)) != len(result):
        _invalid(f"{context} must contain unique ids")
    return result


def _parse_nonempty_text_tuple(value: object, context: str) -> tuple[str, ...]:
    values = _require_list(value, context)
    if not values:
        _invalid(f"{context} must not be empty")
    return tuple(_require_text(item, f"{context}[{index}]") for index, item in enumerate(values))


def _reject_duplicate_normalized_forms(
    values: tuple[str, ...], case_sensitive: bool, context: str
) -> None:
    normalized = tuple(_normalize_visible(value, case_sensitive) for value in values)
    if len(set(normalized)) != len(normalized):
        _invalid(f"{context} contains duplicate accepted forms")


def _require_relative_path(value: object, context: str) -> str:
    path = _require_text(value, context)
    if "\\" in path or "\x00" in path or ":" in path:
        _invalid(f"{context} must use a safe repository-relative POSIX path")
    pure = PurePosixPath(path)
    if (
        pure.is_absolute()
        or path != pure.as_posix()
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        _invalid(f"{context} must not be absolute or contain traversal")
    if not pure.parts or pure.parts[0] != "tests":
        _invalid(f"{context} must stay under tests/")
    return pure.as_posix()


def _require_object(value: object, context: str) -> dict[str, object]:
    if type(value) is not dict:
        _invalid(f"{context} must be a JSON object")
    return value  # type: ignore[return-value]


def _require_list(value: object, context: str) -> list[object]:
    if type(value) is not list:
        _invalid(f"{context} must be a JSON array")
    return value  # type: ignore[return-value]


def _require_keys(document: dict[str, object], expected: set[str], context: str) -> None:
    actual = set(document)
    unknown = sorted(actual - expected)
    missing = sorted(expected - actual)
    if unknown or missing:
        _invalid(f"{context} keys differ; unknown={unknown!r}, missing={missing!r}")


def _require_text(value: object, context: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        _invalid(f"{context} must be nonempty exact text without edge whitespace")
    return value


def _require_optional_text(value: object, context: str) -> str | None:
    if value is None:
        return None
    return _require_text(value, context)


def _require_id(value: object, context: str) -> str:
    identifier = _require_text(value, context)
    if _ID.fullmatch(identifier) is None:
        _invalid(f"{context} is not a restricted lowercase id")
    return identifier


def _require_optional_id(value: object, context: str) -> str | None:
    if value is None:
        return None
    return _require_id(value, context)


def _require_integer(value: object, context: str, *, minimum: int) -> int:
    if type(value) is not int or value < minimum:
        _invalid(f"{context} must be an integer >= {minimum}")
    return value


def _require_optional_integer(
    value: object, context: str, *, minimum: int
) -> int | None:
    if value is None:
        return None
    return _require_integer(value, context, minimum=minimum)


def _require_boolean(value: object, context: str) -> bool:
    if type(value) is not bool:
        _invalid(f"{context} must be an exact boolean")
    return value


def _normalize_visible(value: str, case_sensitive: bool) -> str:
    normalized = unicodedata.normalize("NFKC", value.replace("\r\n", "\n").replace("\r", "\n"))
    normalized = " ".join(normalized.split())
    return normalized if case_sensitive else normalized.casefold()


def _looks_critical_text(value: str) -> bool:
    return any(
        character.isdigit()
        or character in "+-\u2212\u00b1=\u2260<>\u2264\u2265\u00d7\u00f7*/"
        for character in _normalize_visible(value, True)
    )


def _validate_perfect_table_forms(expected: ExpectedMarkdownTable) -> None:
    canonical_headers = tuple(cell.accepted[0] for cell in expected.header)
    header_forms = (canonical_headers,) + tuple(
        tuple(_replace_final_space(header, line_break) for header in canonical_headers)
        for line_break in NEUTRAL_TABLE_LINE_BREAKS
    )
    rows = tuple(tuple(cell.accepted[0] for cell in row) for row in expected.rows)
    separator = tuple("---" for _ in canonical_headers)
    for headers in header_forms:
        markdown = "\n".join(
            "| " + " | ".join(row) + " |"
            for row in (headers, separator, *rows)
        )
        score = score_table_cells(expected, markdown)
        if (
            score.header_accuracy.numerator != score.header_accuracy.denominator
            or score.data_cell_accuracy.numerator != score.data_cell_accuracy.denominator
            or score.critical_accuracy.numerator != score.critical_accuracy.denominator
            or score.unexpected_coordinate_count
            or score.unexpected_critical_cell_count
        ):
            _invalid("table expectations are not a perfect frozen scorer fixture")


def _replace_final_space(value: str, replacement: str) -> str:
    left, separator, right = value.rpartition(" ")
    if not separator or not left or not right:
        _invalid("bilingual table headers must contain one final language separator")
    return f"{left}{replacement}{right}"


def _invalid(message: str) -> NoReturn:
    raise ManifestValidationError(message)
