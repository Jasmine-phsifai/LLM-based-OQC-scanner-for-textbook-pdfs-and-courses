"""Hash every Python file that can affect Phase 1 recognition or scoring."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class HashedQualityFile:
    """One repository-relative code file and its immutable byte evidence."""

    path: str
    bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class QualityCodeBundle:
    """A path-framed aggregate hash plus every contributing file hash."""

    name: str
    sha256: str
    files: tuple[HashedQualityFile, ...]


@dataclass(frozen=True, slots=True)
class Phase1CodeIdentity:
    """Runtime, quality-tooling, and package-metadata code identities."""

    runtime: QualityCodeBundle
    quality: QualityCodeBundle
    packaging: QualityCodeBundle


def hash_quality_bundle(repository_root: str | Path) -> Phase1CodeIdentity:
    """Return deterministic hashes for all files that affect the live gate."""

    unresolved_root = Path(repository_root)
    if unresolved_root.is_symlink() or not unresolved_root.is_dir():
        raise ValueError("repository_root must be a real directory")
    root = unresolved_root.resolve(strict=True)
    return Phase1CodeIdentity(
        runtime=_hash_python_tree(root, "runtime", "src/ocrllm"),
        quality=_hash_python_tree(root, "quality", "quality_lab"),
        packaging=_hash_explicit_files(root, "packaging", ("pyproject.toml",)),
    )


def _hash_python_tree(root: Path, name: str, relative_root: str) -> QualityCodeBundle:
    directory = root / Path(relative_root)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError(f"code root is missing or linked: {relative_root}")
    paths = tuple(
        path
        for path in directory.rglob("*.py")
        if "__pycache__" not in path.parts
    )
    return _hash_paths(root, name, paths)


def _hash_explicit_files(
    root: Path,
    name: str,
    relative_paths: tuple[str, ...],
) -> QualityCodeBundle:
    return _hash_paths(root, name, tuple(root / Path(path) for path in relative_paths))


def _hash_paths(root: Path, name: str, paths: tuple[Path, ...]) -> QualityCodeBundle:
    if not paths:
        raise ValueError(f"{name} code bundle must not be empty")
    records: list[HashedQualityFile] = []
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix()):
        _require_regular_unlinked_path(root, path)
        relative = path.relative_to(root).as_posix()
        payload = path.read_bytes()
        path_bytes = relative.encode("utf-8")
        digest.update(len(path_bytes).to_bytes(8, "big"))
        digest.update(path_bytes)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
        records.append(
            HashedQualityFile(
                path=relative,
                bytes=len(payload),
                sha256=hashlib.sha256(payload).hexdigest(),
            )
        )
    return QualityCodeBundle(name=name, sha256=digest.hexdigest(), files=tuple(records))


def _require_regular_unlinked_path(root: Path, path: Path) -> None:
    current = root
    for part in path.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("code bundle contains a symlink")
    mode = os.stat(path, follow_symlinks=False).st_mode
    if not stat.S_ISREG(mode):
        raise ValueError("code bundle contains a non-regular file")
