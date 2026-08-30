"""Bind Phase 1 evidence inputs to one clean Git commit."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


_OBJECT_ID = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
_RELEVANT_SCOPES = (
    "src/ocrllm",
    "quality_lab",
    "pyproject.toml",
)


@dataclass(frozen=True, slots=True)
class QualityRepositoryIdentity:
    """One clean HEAD and the exact relevant index entries it owns."""

    head_commit: str
    relevant_index_sha256: str
    relevant_file_count: int
    relevant_tree_clean: bool


def capture_quality_repository_identity(
    repository_root: str | Path,
    relevant_paths: Sequence[str],
) -> QualityRepositoryIdentity:
    """Reject dirty or untracked evidence inputs and return their Git identity."""

    unresolved_root = Path(repository_root)
    if unresolved_root.is_symlink() or not unresolved_root.is_dir():
        raise ValueError("repository_root must be a real directory")
    root = unresolved_root.resolve(strict=True)
    normalized_paths = _normalize_relevant_paths(root, relevant_paths)
    top_level = Path(
        _run_git(root, "rev-parse", "--show-toplevel").decode("utf-8").strip()
    ).resolve(strict=True)
    if top_level != root:
        raise ValueError("repository_root must be the exact Git worktree root")

    head_commit = _run_git(root, "rev-parse", "--verify", "HEAD^{commit}").decode(
        "ascii"
    ).strip()
    if _OBJECT_ID.fullmatch(head_commit) is None:
        raise ValueError("Git HEAD did not resolve to one canonical commit")

    scope_pathspecs = tuple(f":(literal){path}" for path in _RELEVANT_SCOPES)
    status = _run_git(
        root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--",
        *scope_pathspecs,
    )
    if status:
        raise ValueError("relevant Phase 1 repository paths are not clean")

    scoped_index_records = _parse_index_records(
        _run_git(root, "ls-files", "--stage", "-z", "--", *scope_pathspecs)
    )
    index_records = {
        path: record
        for path, record in scoped_index_records.items()
        if _is_relevant_scope_file(path)
    }
    if set(index_records) != set(normalized_paths):
        raise ValueError(
            "tracked Phase 1 inventory differs from the relevant file inventory"
        )
    working_object_ids = _hash_working_files(root, normalized_paths)
    if any(
        working_object_ids[path] != index_records[path][1]
        for path in normalized_paths
    ):
        raise ValueError("relevant working files differ from their Git index blobs")

    digest = hashlib.sha256()
    for path in normalized_paths:
        mode, object_id = index_records[path]
        framed = f"{mode} {object_id} {path}".encode("utf-8")
        digest.update(len(framed).to_bytes(8, "big"))
        digest.update(framed)
    return QualityRepositoryIdentity(
        head_commit=head_commit,
        relevant_index_sha256=digest.hexdigest(),
        relevant_file_count=len(normalized_paths),
        relevant_tree_clean=True,
    )


def _normalize_relevant_paths(root: Path, values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError("relevant_paths must be an ordered sequence")
    normalized: list[str] = []
    for value in values:
        if type(value) is not str:
            raise TypeError("relevant_paths must contain exact text")
        pure = PurePosixPath(value)
        if (
            pure.is_absolute()
            or not pure.parts
            or value != pure.as_posix()
            or any(part in {"", ".", ".."} for part in pure.parts)
            or "\\" in value
            or ":" in value
            or "\r" in value
            or "\n" in value
        ):
            raise ValueError("relevant_paths must stay inside the repository")
        path = root / pure
        current = root
        for part in pure.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError("a relevant repository path contains a symlink")
        if not path.is_file() or not path.resolve(strict=True).is_relative_to(root):
            raise ValueError("every relevant repository path must be a regular file")
        normalized.append(value)
    result = tuple(sorted(normalized))
    if not result or len(set(result)) != len(result):
        raise ValueError("relevant_paths must be nonempty and unique")
    return result


def _is_relevant_scope_file(path: str) -> bool:
    return bool(
        path == "pyproject.toml"
        or (path.startswith("src/ocrllm/") and path.endswith(".py"))
        or (path.startswith("quality_lab/") and path.endswith(".py"))
        or path.startswith("quality_lab/assets/")
        or path.startswith("quality_lab/fixtures/phase1/")
    )


def _parse_index_records(payload: bytes) -> dict[str, tuple[str, str]]:
    records: dict[str, tuple[str, str]] = {}
    for raw_record in payload.split(b"\0"):
        if not raw_record:
            continue
        try:
            metadata, raw_path = raw_record.split(b"\t", 1)
            mode, object_id, stage = metadata.decode("ascii").split(" ")
            path = raw_path.decode("utf-8")
        except (UnicodeError, ValueError) as exc:
            raise ValueError("Git returned malformed relevant index evidence") from exc
        if (
            mode not in {"100644", "100755"}
            or _OBJECT_ID.fullmatch(object_id) is None
            or stage != "0"
            or path in records
        ):
            raise ValueError("Git returned invalid relevant index evidence")
        records[path] = (mode, object_id)
    return records


def _hash_working_files(
    root: Path,
    paths: tuple[str, ...],
) -> dict[str, str]:
    payload = "".join(f"{path}\n" for path in paths).encode("utf-8")
    raw_object_ids = _run_git_with_input(
        root,
        payload,
        "hash-object",
        "--stdin-paths",
    ).decode("ascii").splitlines()
    if len(raw_object_ids) != len(paths) or any(
        _OBJECT_ID.fullmatch(object_id) is None for object_id in raw_object_ids
    ):
        raise ValueError("Git could not hash every relevant working file")
    return dict(zip(paths, raw_object_ids, strict=True))


def _run_git(root: Path, *arguments: str) -> bytes:
    return _run_git_process(root, None, arguments)


def _run_git_with_input(root: Path, payload: bytes, *arguments: str) -> bytes:
    return _run_git_process(root, payload, arguments)


def _run_git_process(
    root: Path,
    payload: bytes | None,
    arguments: tuple[str, ...],
) -> bytes:
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        completed = subprocess.run(
            ("git", "-C", str(root), *arguments),
            input=payload,
            stdin=subprocess.DEVNULL if payload is None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            shell=False,
            env=environment,
        )
    except OSError as exc:
        raise ValueError("Git is required for Phase 1 repository identity") from exc
    if completed.returncode != 0:
        raise ValueError("Git could not establish Phase 1 repository identity")
    return completed.stdout
