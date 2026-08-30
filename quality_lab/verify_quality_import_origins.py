"""Prove the live runner imported code from the repository it hashes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import ocrllm
import quality_lab


@dataclass(frozen=True, slots=True)
class QualityImportOrigins:
    """Repository-relative package roots verified for the current process."""

    runtime_package: str
    runtime_relative_root: str
    quality_package: str
    quality_relative_root: str
    runner_relative_path: str
    matches_repository: bool


def verify_quality_import_origins(
    repository_root: str | Path,
    *,
    runner_file: str | Path,
) -> QualityImportOrigins:
    """Reject installed, overlaid, linked, or foreign runtime/quality imports."""

    unresolved_root = Path(repository_root)
    if unresolved_root.is_symlink() or not unresolved_root.is_dir():
        raise ValueError("repository_root must be a real directory")
    root = unresolved_root.resolve(strict=True)
    runtime_root = _require_real_directory(root / "src" / "ocrllm")
    quality_root = _require_real_directory(root / "quality_lab")
    _require_exact_package_origin(ocrllm, runtime_root, "ocrllm")
    _require_exact_package_origin(quality_lab, quality_root, "quality_lab")

    runner_path = Path(runner_file)
    if runner_path.is_symlink() or not runner_path.is_file():
        raise ValueError("quality runner must be one real repository file")
    resolved_runner = runner_path.resolve(strict=True)
    if resolved_runner.parent != quality_root:
        raise ValueError("quality runner was not imported from repository quality_lab")
    return QualityImportOrigins(
        runtime_package="ocrllm",
        runtime_relative_root="src/ocrllm",
        quality_package="quality_lab",
        quality_relative_root="quality_lab",
        runner_relative_path=resolved_runner.relative_to(root).as_posix(),
        matches_repository=True,
    )


def _require_real_directory(path: Path) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise ValueError("expected repository import root is missing or linked")
    return path.resolve(strict=True)


def _require_exact_package_origin(
    package: object,
    expected_root: Path,
    package_name: str,
) -> None:
    package_file = getattr(package, "__file__", None)
    package_paths = getattr(package, "__path__", None)
    if type(package_file) is not str or package_paths is None:
        raise ValueError(f"{package_name} package origin is unavailable")
    try:
        resolved_file = Path(package_file).resolve(strict=True)
        resolved_paths = tuple(Path(value).resolve(strict=True) for value in package_paths)
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError(f"{package_name} package origin could not be verified") from exc
    if resolved_file != expected_root / "__init__.py" or resolved_paths != (
        expected_root,
    ):
        raise ValueError(f"{package_name} was not imported from the repository")
