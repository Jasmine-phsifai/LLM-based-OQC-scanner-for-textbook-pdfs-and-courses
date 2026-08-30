from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import quality_lab as quality_package

from quality_lab.capture_quality_repository_identity import (
    capture_quality_repository_identity,
)
from quality_lab.hash_quality_bundle import hash_quality_bundle
from quality_lab.load_fixture_manifest import load_fixture_manifest
from quality_lab.score_recognition_result import score_recognition_result
from quality_lab.serialize_recognition_quality_report import (
    serialize_recognition_quality_report,
)
from quality_lab.write_quality_evidence_atomically import (
    QualityEvidenceWriteError,
    write_quality_evidence_atomically,
)
from quality_lab.verify_quality_import_origins import verify_quality_import_origins


def test_code_bundle_hash_is_stable_and_path_framed(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    runtime = root / "src" / "ocrllm"
    quality = root / "quality_lab"
    runtime.mkdir(parents=True)
    quality.mkdir(parents=True)
    (runtime / "a.py").write_text("A = 1\n", encoding="utf-8")
    (quality / "b.py").write_text("B = 2\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")

    first = hash_quality_bundle(root)
    second = hash_quality_bundle(root)

    assert first == second
    assert first.runtime.files[0].path == "src/ocrllm/a.py"
    assert first.quality.files[0].path == "quality_lab/b.py"
    (quality / "b.py").write_text("B = 3\n", encoding="utf-8")
    changed = hash_quality_bundle(root)
    assert changed.runtime == first.runtime
    assert changed.quality.sha256 != first.quality.sha256

    link = tmp_path / "linked-repo"
    try:
        link.symlink_to(root, target_is_directory=True)
    except OSError:
        pass
    else:
        with pytest.raises(ValueError, match="real directory"):
            hash_quality_bundle(link)


def test_atomic_evidence_writer_refuses_overwrite_and_credentials(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    secret = "secret-sentinel"

    write_quality_evidence_atomically(
        path,
        {"state": "running"},
        credential=secret,
        replace_existing=False,
    )
    assert json.loads(path.read_text(encoding="utf-8")) == {"state": "running"}
    with pytest.raises(QualityEvidenceWriteError, match="already exists"):
        write_quality_evidence_atomically(
            path,
            {"state": "wrong"},
            credential=secret,
            replace_existing=False,
        )
    write_quality_evidence_atomically(
        path,
        {"state": "complete"},
        credential=secret,
        replace_existing=True,
    )
    assert json.loads(path.read_text(encoding="utf-8")) == {"state": "complete"}
    with pytest.raises(QualityEvidenceWriteError, match="sensitive"):
        write_quality_evidence_atomically(
            path,
            {"markdown": f"leaked {secret}"},
            credential=secret,
            replace_existing=True,
        )
    assert secret not in path.read_text(encoding="utf-8")

    escaped_secret = 'sk-valid"quoted\\key'
    escaped_path = tmp_path / "escaped-secret.json"
    with pytest.raises(QualityEvidenceWriteError, match="sensitive"):
        write_quality_evidence_atomically(
            escaped_path,
            {"markdown": escaped_secret},
            credential=escaped_secret,
            replace_existing=False,
        )
    assert not escaped_path.exists()

    base_url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    with pytest.raises(QualityEvidenceWriteError, match="sensitive"):
        write_quality_evidence_atomically(
            path,
            {"markdown": base_url},
            credential=secret,
            forbidden_values=(base_url,),
            replace_existing=True,
        )
    assert base_url not in path.read_text(encoding="utf-8")


def test_repository_identity_rejects_dirty_deleted_untracked_and_hidden_changes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    runtime_file = root / "src" / "ocrllm" / "a.py"
    quality_file = root / "quality_lab" / "b.py"
    manifest_file = root / "quality_lab" / "fixtures" / "phase1" / "manifest.json"
    for path, payload in (
        (runtime_file, "A = 1\n"),
        (quality_file, "B = 2\n"),
        (manifest_file, "{}\n"),
        (root / "pyproject.toml", "[project]\nname='identity-test'\n"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
    _git(root, "init")
    _git(root, "config", "user.email", "quality@example.invalid")
    _git(root, "config", "user.name", "Quality Test")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "fixture")
    relevant = (
        "pyproject.toml",
        "src/ocrllm/a.py",
        "quality_lab/fixtures/phase1/manifest.json",
        "quality_lab/b.py",
    )

    identity = capture_quality_repository_identity(root, relevant)
    assert identity.relevant_tree_clean is True
    assert identity.relevant_file_count == 4

    runtime_file.write_text("A = 9\n", encoding="utf-8")
    with pytest.raises(ValueError):
        capture_quality_repository_identity(root, relevant)
    runtime_file.write_text("A = 1\n", encoding="utf-8")

    _git(root, "update-index", "--assume-unchanged", "src/ocrllm/a.py")
    runtime_file.write_text("A = 7\n", encoding="utf-8")
    with pytest.raises(ValueError, match="index blobs"):
        capture_quality_repository_identity(root, relevant)
    _git(root, "update-index", "--no-assume-unchanged", "src/ocrllm/a.py")
    runtime_file.write_text("A = 1\n", encoding="utf-8")

    quality_file.unlink()
    with pytest.raises(ValueError):
        capture_quality_repository_identity(root, relevant)
    quality_file.write_text("B = 2\n", encoding="utf-8")

    (quality_file.parent / "extra.py").write_text("EXTRA = 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not clean"):
        capture_quality_repository_identity(root, relevant)


def test_import_origins_bind_runtime_and_quality_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Path(__file__).parents[2]

    origins = verify_quality_import_origins(
        root,
        runner_file=root / "quality_lab" / "run_phase1_quality.py",
    )

    assert origins.runtime_relative_root == "src/ocrllm"
    assert origins.quality_package == "quality_lab"
    assert origins.quality_relative_root == "quality_lab"

    monkeypatch.setattr(
        quality_package,
        "__path__",
        [str(root / "tests")],
    )
    with pytest.raises(ValueError, match="not imported from the repository"):
        verify_quality_import_origins(
            root,
            runner_file=root / "quality_lab" / "run_phase1_quality.py",
        )


def _git(root: Path, *arguments: str) -> None:
    subprocess.run(
        ("git", "-C", str(root), *arguments),
        check=True,
        capture_output=True,
        text=True,
    )


def test_integrated_report_serialization_keeps_exact_rational_counts() -> None:
    manifest = load_fixture_manifest()
    dispatch = manifest.live_dispatch_order[2]
    fixture = next(item for item in manifest.fixtures if item.id == dispatch.fixture_ids[0])
    markdown = "\n".join(unit.text for unit in fixture.content_units)

    serialized = serialize_recognition_quality_report(
        score_recognition_result(manifest, dispatch, markdown)
    )

    assert serialized["text"]["recall"] == {"numerator": 30, "denominator": 30}
    assert serialized["critical_slots"]["accuracy"] == {
        "numerator": 10,
        "denominator": 10,
    }
    assert serialized["languages"][0]["language"] == "en-US"
    assert serialized["formulas"] is None
    assert serialized["table"] is None
    assert serialized["ordered_anchors"] is None
    assert serialized["passes"] is True
