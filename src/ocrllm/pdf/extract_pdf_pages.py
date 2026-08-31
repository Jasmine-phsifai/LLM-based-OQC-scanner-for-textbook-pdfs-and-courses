"""Publish every page of one PDF as an ordered caller-owned PNG tuple."""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path
from uuid import uuid4

from ..errors import OCRLLMError, OutputError, OutputExists
from ..output.claim_output_target import claim_output_target
from ..output.normalize_output_stem import normalize_output_stem
from .inspect_pdf import inspect_pdf
from .render_pdf_page_group import render_pdf_page_group
from .snapshot_pdf import snapshot_pdf


_PDF_PAGE_GROUP_SIZE = 8


def extract_pdf_pages(
    source: str | Path,
    *,
    output_dir: str | Path | None = None,
) -> tuple[Path, ...]:
    """Atomically publish full PDF pages without provider work or later cleanup."""
    source_path = Path(source)
    target_root = _resolve_pdf_page_target(source_path, output_dir=output_dir)
    _preflight_pdf_page_target(target_root)

    with claim_output_target(target_root):
        _preflight_pdf_page_target(target_root)
        return _extract_pdf_pages_to_target(source_path, target_root=target_root)


def _resolve_pdf_page_target(
    source_path: Path,
    *,
    output_dir: str | Path | None,
) -> Path:
    if output_dir is not None:
        return Path(output_dir)
    return source_path.parent / normalize_output_stem(source_path.stem)


def _preflight_pdf_page_target(target_root: Path) -> None:
    try:
        parent_info = os.lstat(target_root.parent)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        parent_is_reparse = bool(
            getattr(parent_info, "st_file_attributes", 0) & reparse_flag
        )
        if not stat.S_ISDIR(parent_info.st_mode) or parent_is_reparse:
            raise OutputError(
                "The PDF page output parent must be a plain directory.",
                code="OUTPUT_PATH_INVALID",
            ) from None
        if os.path.lexists(target_root):
            raise OutputExists(
                "The requested PDF page output directory already exists."
            ) from None
    except (OutputError, OutputExists):
        raise
    except (OSError, ValueError) as error:
        raise OutputError(
            "The PDF page output path could not be inspected.",
            code="OUTPUT_PATH_INVALID",
        ) from error


def _extract_pdf_pages_to_target(
    source_path: Path,
    *,
    target_root: Path,
) -> tuple[Path, ...]:
    staging_root = target_root.parent / f".ocrllm-pdf-{uuid4().hex[:16]}.tmp"
    primary_error: BaseException | None = None
    published = False
    try:
        _prepare_pdf_page_staging(staging_root, target_root=target_root)
        staged_paths: tuple[Path, ...]
        with snapshot_pdf(source_path, temp_dir=None) as snapshot:
            page_sizes = inspect_pdf(snapshot.path)
            staged_paths = _render_pdf_pages_to_staging(
                snapshot.path,
                page_sizes,
                staging_root=staging_root,
            )
        _publish_pdf_page_directory(staging_root, target_root=target_root)
        published = True
        return tuple(target_root / path.name for path in staged_paths)
    except BaseException as error:
        primary_error = error
        raise
    finally:
        if not published:
            _remove_pdf_page_staging(staging_root, primary_error=primary_error)


def _prepare_pdf_page_staging(staging_root: Path, *, target_root: Path) -> None:
    _preflight_pdf_page_target(target_root)
    try:
        staging_root.mkdir()
    except (OSError, ValueError) as error:
        raise OutputError(
            "The temporary PDF page directory could not be created.",
            code="OUTPUT_WRITE_FAILED",
        ) from error


def _render_pdf_pages_to_staging(
    snapshot_path: Path,
    page_sizes: tuple[tuple[float, float], ...],
    *,
    staging_root: Path,
) -> tuple[Path, ...]:
    transient_root = staging_root / ".rendered"
    staged_paths: list[Path] = []
    for first_index in range(0, len(page_sizes), _PDF_PAGE_GROUP_SIZE):
        indexes = tuple(
            range(
                first_index,
                min(first_index + _PDF_PAGE_GROUP_SIZE, len(page_sizes)),
            )
        )
        with render_pdf_page_group(
            snapshot_path,
            indexes,
            page_sizes,
            output_directory=transient_root,
            cancellation=None,
        ) as rendered_paths:
            for page_index, rendered_path in zip(indexes, rendered_paths, strict=True):
                staged_path = staging_root / rendered_path.name
                _move_rendered_pdf_page(
                    rendered_path,
                    staged_path,
                    page_number=page_index + 1,
                )
                staged_paths.append(staged_path)
    try:
        transient_root.rmdir()
    except (OSError, ValueError) as error:
        raise OutputError(
            "The temporary PDF render directory could not be finalized.",
            code="OUTPUT_WRITE_FAILED",
        ) from error
    return tuple(staged_paths)


def _move_rendered_pdf_page(
    rendered_path: Path,
    staged_path: Path,
    *,
    page_number: int,
) -> None:
    try:
        os.replace(rendered_path, staged_path)
    except (OSError, ValueError) as error:
        raise OutputError(
            "A rendered PDF page could not be retained for publication.",
            code="OUTPUT_WRITE_FAILED",
            details={"page_number": page_number},
        ) from error


def _publish_pdf_page_directory(staging_root: Path, *, target_root: Path) -> None:
    _preflight_pdf_page_target(target_root)
    try:
        os.rename(staging_root, target_root)
    except FileExistsError as error:
        raise OutputExists(
            "The requested PDF page output directory already exists."
        ) from error
    except (OSError, ValueError) as error:
        if os.path.lexists(target_root):
            raise OutputExists(
                "The requested PDF page output directory already exists."
            ) from error
        raise OutputError(
            "The PDF page directory could not be published.",
            code="OUTPUT_WRITE_FAILED",
        ) from error


def _remove_pdf_page_staging(
    staging_root: Path,
    *,
    primary_error: BaseException | None,
) -> None:
    if not os.path.lexists(staging_root):
        return
    try:
        shutil.rmtree(staging_root)
    except (OSError, ValueError) as error:
        if primary_error is None:
            raise OutputError(
                "The temporary PDF page directory could not be removed.",
                code="OUTPUT_WRITE_FAILED",
            ) from error
        if isinstance(primary_error, OCRLLMError):
            primary_error._add_safe_detail("pdf_page_output_cleanup_failed", True)
