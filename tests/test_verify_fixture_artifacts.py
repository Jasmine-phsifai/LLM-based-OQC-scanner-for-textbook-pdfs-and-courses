from __future__ import annotations

import hashlib
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from tests.quality.fixture_manifest import ArtifactRecord, LicenseRecord
from tests.quality.load_fixture_manifest import load_fixture_manifest
from tests.quality.verify_fixture_artifacts import (
    ArtifactVerificationError,
    verify_fixture_artifacts,
)


def test_verifies_every_hash_image_license_and_provenance_offline() -> None:
    manifest = load_fixture_manifest()

    report = verify_fixture_artifacts(manifest)

    assert report.artifact_count == 20
    assert report.fixture_image_count == 5
    assert report.total_bytes == 17_887_099 + manifest.raw_bytes
    assert report.total_bytes <= 25 * 1024 * 1024


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("sha256", "0" * 64, "SHA-256"),
        ("bytes", 1, "byte size"),
        ("pixel_width", 1, "dimensions"),
    ],
)
def test_rejects_artifact_hash_size_or_decoded_dimension_drift(
    field: str, value: object, message: str
) -> None:
    manifest = load_fixture_manifest()
    changed = replace(manifest.artifacts[0], **{field: value})
    mutated = replace(manifest, artifacts=(changed,) + manifest.artifacts[1:])

    with pytest.raises(ArtifactVerificationError, match=message):
        verify_fixture_artifacts(mutated)


def test_rejects_defensive_path_traversal_even_for_constructed_records() -> None:
    manifest = load_fixture_manifest()
    changed = replace(manifest.artifacts[0], path="tests/../outside.png")
    mutated = replace(manifest, artifacts=(changed,) + manifest.artifacts[1:])

    with pytest.raises(ArtifactVerificationError, match="escapes"):
        verify_fixture_artifacts(mutated)


def test_rejects_corpus_over_the_committed_ceiling() -> None:
    manifest = load_fixture_manifest()
    mutated = replace(manifest, max_corpus_bytes=17_879_114 + manifest.raw_bytes)

    with pytest.raises(ArtifactVerificationError, match="exceeds 25 MiB"):
        verify_fixture_artifacts(mutated)


def test_rejects_symlinked_artifact_without_following_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    tests_dir = root / "tests"
    tests_dir.mkdir(parents=True)
    link = tests_dir / "linked.txt"
    link.write_text("immutable", encoding="utf-8")
    original_is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: path == link or original_is_symlink(path),
    )

    manifest = load_fixture_manifest()
    artifact = ArtifactRecord(
        id="linked-artifact",
        path="tests/linked.txt",
        sha256=hashlib.sha256(b"immutable").hexdigest(),
        bytes=len(b"immutable"),
        role="generator-source",
        redistribution="allowed",
        license_id="repo-owned-test-data",
        media_type=None,
        pixel_width=None,
        pixel_height=None,
    )
    minimal = replace(
        manifest,
        artifacts=(artifact,),
        licenses=(),
        fixtures=(),
        ordered_requests=(),
    )

    with pytest.raises(ArtifactVerificationError, match="symlink"):
        verify_fixture_artifacts(minimal, repository_root=root)


def test_rejects_license_text_that_does_not_match_spdx(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    license_path = root / "tests" / "license.txt"
    license_path.parent.mkdir(parents=True)
    license_path.write_text("not a real license", encoding="utf-8")
    payload = license_path.read_bytes()
    manifest = load_fixture_manifest()
    artifact = ArtifactRecord(
        id="license-evidence",
        path="tests/license.txt",
        sha256=hashlib.sha256(payload).hexdigest(),
        bytes=len(payload),
        role="license",
        redistribution="evidence_copy",
        license_id=None,
        media_type=None,
        pixel_width=None,
        pixel_height=None,
    )
    license = LicenseRecord(
        id="cc0-whiteboard",
        spdx="CC0-1.0",
        redistribution="allowed",
        license_artifact_id="license-evidence",
        provenance_artifact_id=None,
    )
    minimal = replace(
        manifest,
        artifacts=(artifact,),
        licenses=(license,),
        fixtures=(),
        ordered_requests=(),
    )

    with pytest.raises(ArtifactVerificationError, match="SPDX"):
        verify_fixture_artifacts(minimal, repository_root=root)


def test_rejects_license_reassignment_that_breaks_provenance_binding() -> None:
    manifest = load_fixture_manifest()
    index = next(
        index
        for index, artifact in enumerate(manifest.artifacts)
        if artifact.id == "handwritten-whiteboard-image"
    )
    changed = replace(manifest.artifacts[index], license_id="repo-owned-test-data")
    artifacts = list(manifest.artifacts)
    artifacts[index] = changed
    mutated = replace(manifest, artifacts=tuple(artifacts))

    with pytest.raises(ArtifactVerificationError, match="CC0 provenance"):
        verify_fixture_artifacts(mutated)


def test_rejects_undeclared_file_in_any_frozen_corpus_root(tmp_path: Path) -> None:
    manifest = load_fixture_manifest()
    root = tmp_path / "repo"
    source_root = Path(__file__).resolve().parents[1]
    manifest_path = source_root / "tests" / "fixtures" / "phase1" / "manifest.json"
    target_manifest = root / "tests" / "fixtures" / "phase1" / "manifest.json"
    target_manifest.parent.mkdir(parents=True)
    shutil.copyfile(manifest_path, target_manifest)
    for artifact in manifest.artifacts:
        source = source_root / artifact.path
        target = root / artifact.path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    extra = root / "tests" / "quality" / "generators" / "undeclared.py"
    extra.write_text("UNDECLARED = True\n", encoding="utf-8")

    with pytest.raises(ArtifactVerificationError, match="undeclared.py"):
        verify_fixture_artifacts(manifest, repository_root=root)


def test_rejects_manifest_drift_after_loading(tmp_path: Path) -> None:
    manifest = load_fixture_manifest()
    root = tmp_path / "repo"
    source_root = Path(__file__).resolve().parents[1]
    for artifact in manifest.artifacts:
        source = source_root / artifact.path
        target = root / artifact.path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    manifest_path = root / "tests" / "fixtures" / "phase1" / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(
        (source_root / "tests" / "fixtures" / "phase1" / "manifest.json").read_bytes()
        + b"\n"
    )

    with pytest.raises(ArtifactVerificationError, match="changed after load"):
        verify_fixture_artifacts(manifest, repository_root=root)
