"""Verify Phase 1 corpus files, licenses, and provenance without network access."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from quality_lab.fixture_manifest import (
    ArtifactRecord,
    LicenseRecord,
    Phase1FixtureManifest,
)


DEFAULT_REPOSITORY_ROOT = Path(__file__).parents[1]
_READ_CHUNK_BYTES = 1024 * 1024
_FROZEN_SCHEMA_VERSION = "ocrllm.phase1-fixture-manifest.v1"
_FROZEN_CORPUS_ID = "phase1-image-quality.v1"
_MANIFEST_RELATIVE_PATH = "quality_lab/fixtures/phase1/manifest.json"
_CORPUS_INVENTORY_ROOTS = (
    "quality_lab/fixtures/phase1",
    "quality_lab/assets/fonts",
    "quality_lab/generators",
)


class ArtifactVerificationError(ValueError):
    """A local corpus artifact differs from its committed evidence record."""


@dataclass(frozen=True, slots=True)
class ArtifactVerificationReport:
    """Exact offline verification totals for the committed corpus."""

    artifact_count: int
    fixture_image_count: int
    total_bytes: int


def verify_fixture_artifacts(
    manifest: Phase1FixtureManifest,
    *,
    repository_root: str | Path = DEFAULT_REPOSITORY_ROOT,
) -> ArtifactVerificationReport:
    """Fail closed on missing, linked, resized, re-encoded, or relicensed files."""

    if type(manifest) is not Phase1FixtureManifest:
        raise TypeError("manifest must be an exact Phase1FixtureManifest")
    root = Path(repository_root)
    if root.is_symlink() or not root.is_dir():
        raise ArtifactVerificationError("repository_root must be a real directory")
    resolved_root = root.resolve(strict=True)
    paths_by_id: dict[str, Path] = {}
    if manifest.raw_bytes <= 0 or len(manifest.raw_sha256) != 64:
        raise ArtifactVerificationError("manifest raw-byte evidence is invalid")
    if _uses_frozen_inventory(manifest):
        _verify_manifest_bytes(resolved_root, manifest)
    total_bytes = manifest.raw_bytes
    fixture_image_count = 0
    for artifact in manifest.artifacts:
        path = _resolve_unlinked_artifact_path(resolved_root, artifact)
        actual_bytes = path.stat().st_size
        if actual_bytes != artifact.bytes:
            raise ArtifactVerificationError(
                f"artifact {artifact.id!r} byte size differs from the manifest"
            )
        if _calculate_sha256(path) != artifact.sha256:
            raise ArtifactVerificationError(
                f"artifact {artifact.id!r} SHA-256 differs from the manifest"
            )
        if artifact.role == "fixture-image":
            _verify_fixture_image(path, artifact)
            fixture_image_count += 1
        paths_by_id[artifact.id] = path
        total_bytes += actual_bytes

    if _uses_frozen_inventory(manifest):
        _verify_exact_corpus_inventory(resolved_root, manifest)
    if total_bytes > manifest.max_corpus_bytes:
        raise ArtifactVerificationError("committed Phase 1 corpus exceeds 25 MiB")
    _verify_local_license_evidence(manifest, paths_by_id)
    _verify_embedded_provenance(manifest, paths_by_id)
    return ArtifactVerificationReport(
        artifact_count=len(manifest.artifacts),
        fixture_image_count=fixture_image_count,
        total_bytes=total_bytes,
    )


def _uses_frozen_inventory(manifest: Phase1FixtureManifest) -> bool:
    return bool(
        manifest.schema_version == _FROZEN_SCHEMA_VERSION
        and manifest.corpus_id == _FROZEN_CORPUS_ID
        and len(manifest.fixtures) == 5
        and len(manifest.licenses) == 3
        and len(manifest.ordered_requests) == 1
        and len(manifest.live_dispatch_order) == 6
    )


def _verify_manifest_bytes(root: Path, manifest: Phase1FixtureManifest) -> None:
    path = root / PurePosixPath(_MANIFEST_RELATIVE_PATH)
    if path.is_symlink() or not path.is_file():
        raise ArtifactVerificationError("committed manifest must be a real file")
    if path.stat().st_size != manifest.raw_bytes:
        raise ArtifactVerificationError("committed manifest byte size changed after load")
    if _calculate_sha256(path) != manifest.raw_sha256:
        raise ArtifactVerificationError("committed manifest SHA-256 changed after load")


def _verify_exact_corpus_inventory(
    root: Path,
    manifest: Phase1FixtureManifest,
) -> None:
    declared = {artifact.path for artifact in manifest.artifacts}
    declared.add(_MANIFEST_RELATIVE_PATH)
    actual: set[str] = set()
    for relative_root in _CORPUS_INVENTORY_ROOTS:
        inventory_root = root / PurePosixPath(relative_root)
        if inventory_root.is_symlink() or not inventory_root.is_dir():
            raise ArtifactVerificationError(
                f"corpus inventory root is missing or linked: {relative_root}"
            )
        actual.update(_enumerate_unlinked_files(root, inventory_root))
    if actual != declared:
        undeclared = sorted(actual - declared)
        missing = sorted(declared - actual)
        raise ArtifactVerificationError(
            "corpus inventory differs from the manifest; "
            f"undeclared={undeclared!r}, missing={missing!r}"
        )


def _enumerate_unlinked_files(root: Path, inventory_root: Path) -> set[str]:
    files: set[str] = set()
    pending = [inventory_root]
    while pending:
        directory = pending.pop()
        try:
            entries = tuple(os.scandir(directory))
        except OSError as exc:
            raise ArtifactVerificationError("corpus inventory could not be read") from exc
        for entry in entries:
            path = Path(entry.path)
            if entry.is_symlink():
                raise ArtifactVerificationError(
                    "corpus inventory contains a symlink"
                )
            if entry.is_dir(follow_symlinks=False):
                pending.append(path)
                continue
            if not entry.is_file(follow_symlinks=False):
                raise ArtifactVerificationError(
                    "corpus inventory contains a non-regular entry"
                )
            if "__pycache__" in path.parts and path.suffix == ".pyc":
                continue
            files.add(path.relative_to(root).as_posix())
    return files


def _resolve_unlinked_artifact_path(root: Path, artifact: ArtifactRecord) -> Path:
    if type(artifact) is not ArtifactRecord:
        raise TypeError("manifest artifacts must be exact ArtifactRecord values")
    pure = PurePosixPath(artifact.path)
    if (
        pure.is_absolute()
        or not pure.parts
        or pure.parts[0] != "quality_lab"
        or artifact.path != pure.as_posix()
        or any(part in {"", ".", ".."} for part in pure.parts)
        or "\\" in artifact.path
        or ":" in artifact.path
    ):
        raise ArtifactVerificationError(
            f"artifact {artifact.id!r} path escapes the quality_lab tree"
        )

    current = root
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise ArtifactVerificationError(
                f"artifact {artifact.id!r} path contains a symlink"
            )
        if not os.path.lexists(current):
            raise ArtifactVerificationError(f"artifact {artifact.id!r} is missing")
    try:
        mode = os.stat(current, follow_symlinks=False).st_mode
    except OSError as exc:
        raise ArtifactVerificationError(
            f"artifact {artifact.id!r} could not be inspected"
        ) from exc
    if not stat.S_ISREG(mode):
        raise ArtifactVerificationError(f"artifact {artifact.id!r} is not a regular file")
    if not current.resolve(strict=True).is_relative_to(root):
        raise ArtifactVerificationError(
            f"artifact {artifact.id!r} resolves outside repository_root"
        )
    return current


def _calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_READ_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_fixture_image(path: Path, artifact: ArtifactRecord) -> None:
    try:
        from PIL import Image
    except (ImportError, ModuleNotFoundError) as exc:
        raise ArtifactVerificationError(
            "Pillow is required to verify decoded fixture dimensions"
        ) from exc

    expected_format = {"image/png": "PNG", "image/jpeg": "JPEG"}.get(
        artifact.media_type
    )
    if expected_format is None:
        raise ArtifactVerificationError(
            f"fixture {artifact.id!r} has unsupported media metadata"
        )
    try:
        with Image.open(path) as image:
            actual_format = image.format
            actual_size = image.size
            image.verify()
    except Exception as exc:
        raise ArtifactVerificationError(
            f"fixture {artifact.id!r} is not a valid decoded image"
        ) from exc
    if actual_format != expected_format:
        raise ArtifactVerificationError(
            f"fixture {artifact.id!r} encoded format differs from the manifest"
        )
    if actual_size != (artifact.pixel_width, artifact.pixel_height):
        raise ArtifactVerificationError(
            f"fixture {artifact.id!r} dimensions differ from the manifest"
        )


def _verify_local_license_evidence(
    manifest: Phase1FixtureManifest, paths_by_id: dict[str, Path]
) -> None:
    required_markers = {
        "LicenseRef-OCRLLM-Repo-Owned-Test-Data": (
            "LicenseRef-OCRLLM-Repo-Owned-Test-Data",
            "Permission:",
        ),
        "CC0-1.0": ("Creative Commons Legal Code", "CC0 1.0 Universal"),
        "OFL-1.1": ("SIL OPEN FONT LICENSE Version 1.1", "PERMISSION & CONDITIONS"),
    }
    for license in manifest.licenses:
        if type(license) is not LicenseRecord:
            raise TypeError("manifest licenses must be exact LicenseRecord values")
        path = paths_by_id.get(license.license_artifact_id)
        if path is None:
            raise ArtifactVerificationError(
                f"license {license.id!r} has no verified local evidence"
            )
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ArtifactVerificationError(
                f"license {license.id!r} evidence is not UTF-8 text"
            ) from exc
        markers = required_markers.get(license.spdx)
        if markers is None or any(marker not in text for marker in markers):
            raise ArtifactVerificationError(
                f"license {license.id!r} evidence does not match its SPDX record"
            )


def _verify_embedded_provenance(
    manifest: Phase1FixtureManifest, paths_by_id: dict[str, Path]
) -> None:
    artifacts_by_id = {artifact.id: artifact for artifact in manifest.artifacts}
    licensed_artifacts: dict[str, list[ArtifactRecord]] = {}
    for artifact in manifest.artifacts:
        if artifact.license_id is not None:
            licensed_artifacts.setdefault(artifact.license_id, []).append(artifact)

    for license in manifest.licenses:
        if license.provenance_artifact_id is None:
            continue
        provenance_path = paths_by_id[license.provenance_artifact_id]
        provenance = _read_strict_json(provenance_path, license.id)
        assets = licensed_artifacts.get(license.id, [])
        if license.spdx == "CC0-1.0":
            _verify_handwritten_provenance(
                provenance,
                assets,
                artifacts_by_id[license.license_artifact_id],
            )
        elif license.spdx == "OFL-1.1":
            _verify_font_provenance(
                provenance,
                assets,
                artifacts_by_id[license.license_artifact_id],
            )
        else:
            raise ArtifactVerificationError(
                f"license {license.id!r} has unexpected provenance"
            )


def _verify_handwritten_provenance(
    provenance: dict[str, object],
    assets: list[ArtifactRecord],
    license_artifact: ArtifactRecord,
) -> None:
    images = [artifact for artifact in assets if artifact.role == "fixture-image"]
    if len(images) != 1:
        raise ArtifactVerificationError("CC0 provenance must bind exactly one fixture")
    image = images[0]
    expected = {
        "schema_version": "ocrllm.external-fixture-provenance.v1",
        "license_spdx": "CC0-1.0",
        "license_path": license_artifact.path,
        "license_sha256": license_artifact.sha256,
        "fixture_path": image.path,
        "fixture_bytes": image.bytes,
        "fixture_width": image.pixel_width,
        "fixture_height": image.pixel_height,
        "fixture_sha256": image.sha256,
        "redistribution": "allowed",
    }
    _require_provenance_values(provenance, expected, "handwritten whiteboard")
    source_sha1 = provenance.get("canonical_original_sha1")
    if type(source_sha1) is not str or len(source_sha1) != 40:
        raise ArtifactVerificationError(
            "handwritten whiteboard provenance lacks the canonical source SHA-1"
        )


def _verify_font_provenance(
    provenance: dict[str, object],
    assets: list[ArtifactRecord],
    license_artifact: ArtifactRecord,
) -> None:
    fonts = [artifact for artifact in assets if artifact.role == "generator-input"]
    if len(fonts) != 1:
        raise ArtifactVerificationError("font provenance must bind exactly one input")
    font = fonts[0]
    expected = {
        "schema_version": "ocrllm.quality-font-provenance.v1",
        "artifact_path": font.path,
        "artifact_bytes": font.bytes,
        "artifact_sha256": font.sha256,
        "license_spdx": "OFL-1.1",
        "license_path": license_artifact.path,
        "redistribution": "allowed_unmodified_with_license",
    }
    _require_provenance_values(provenance, expected, "quality font")
    upstream_commit = provenance.get("upstream_commit")
    if type(upstream_commit) is not str or len(upstream_commit) != 40:
        raise ArtifactVerificationError("font provenance lacks a pinned upstream commit")


def _read_strict_json(path: Path, context: str) -> dict[str, object]:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ArtifactVerificationError(
                    f"{context} provenance contains a duplicate key"
                )
            result[key] = value
        return result

    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)
    except ArtifactVerificationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactVerificationError(f"{context} provenance is not strict JSON") from exc
    if type(value) is not dict:
        raise ArtifactVerificationError(f"{context} provenance must be a JSON object")
    return value


def _require_provenance_values(
    provenance: dict[str, object], expected: dict[str, object], context: str
) -> None:
    mismatched = [
        key for key, expected_value in expected.items() if provenance.get(key) != expected_value
    ]
    if mismatched:
        raise ArtifactVerificationError(
            f"{context} provenance differs at {sorted(mismatched)!r}"
        )
