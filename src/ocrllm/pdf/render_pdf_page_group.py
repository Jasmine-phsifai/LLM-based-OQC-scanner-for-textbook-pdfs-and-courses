"""Render and clean one bounded ordered PDF page group."""

from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from ..errors import InvalidSource, OCRLLMError, OutputError, PDFError
from ..image_group_limits import MAX_AGGREGATE_PIXELS
from ..imaging.decode_image import decode_image
from ..raise_if_cancelled import raise_if_cancelled
from .calculate_pdf_render_scale import calculate_pdf_render_scale
from .open_pdf_document import open_pdf_document
from .pdfium_lock import PDFIUM_LOCK


@contextmanager
def render_pdf_page_group(
    snapshot_path: Path,
    page_indexes: Sequence[int],
    page_sizes: Sequence[tuple[float, float]],
    *,
    output_directory: Path,
    cancellation: object | None,
) -> Iterator[tuple[Path, ...]]:
    """Yield stable PNG paths while holding no live PDFium objects."""
    indexes = tuple(page_indexes)
    if not indexes or len(indexes) > 8:
        raise PDFError(
            "A PDF render group must contain between one and eight pages.",
            code="PDF_PAGE_RANGE_INVALID",
        ) from None
    if any(
        type(index) is not int or not 0 <= index < len(page_sizes)
        for index in indexes
    ):
        raise PDFError(
            "A PDF render group contains an invalid page index.",
            code="PDF_PAGE_RANGE_INVALID",
        ) from None
    try:
        output_directory.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as error:
        raise OutputError(
            "The PDF render directory could not be prepared.",
            code="OUTPUT_WRITE_FAILED",
        ) from error

    rendered_paths: list[Path] = []
    primary_error: BaseException | None = None
    try:
        with PDFIUM_LOCK:
            with open_pdf_document(snapshot_path) as document:
                maximum_page_pixels = MAX_AGGREGATE_PIXELS // len(indexes)
                for page_index in indexes:
                    raise_if_cancelled(cancellation)
                    target_path = output_directory / f"page-{page_index + 1:06d}.png"
                    rendered_paths.append(target_path)
                    _render_one_page(
                        document,
                        page_index,
                        page_sizes[page_index],
                        target_path,
                        maximum_pixels=maximum_page_pixels,
                    )
        yield tuple(rendered_paths)
    except BaseException as error:
        primary_error = error
        raise
    finally:
        cleanup_failed = False
        for rendered_path in rendered_paths:
            try:
                rendered_path.unlink(missing_ok=True)
            except (OSError, ValueError):
                cleanup_failed = True
        if cleanup_failed:
            if primary_error is None:
                raise OutputError(
                    "Rendered PDF pages could not be removed after recognition.",
                    code="OUTPUT_WRITE_FAILED",
                ) from None
            if isinstance(primary_error, OCRLLMError):
                primary_error._add_safe_detail("pdf_render_cleanup_failed", True)


def _render_one_page(
    document,
    page_index: int,
    page_size: tuple[float, float],
    target_path: Path,
    *,
    maximum_pixels: int,
) -> None:
    temporary_path = target_path.with_name(
        f".p-{uuid4().hex[:16]}.tmp.png"
    )
    page = None
    bitmap = None
    image = None
    primary_error: BaseException | None = None
    try:
        try:
            page = document.get_page(page_index)
            scale = calculate_pdf_render_scale(
                *page_size,
                maximum_pixels=maximum_pixels,
            )
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil()
            image.save(temporary_path, format="PNG")
            image.close()
            image = None
            _make_file_durable(temporary_path)
            try:
                decode_image(temporary_path)
            except InvalidSource as error:
                raise OutputError(
                    "A rendered PDF page could not be decoded safely.",
                    code="OUTPUT_WRITE_FAILED",
                    details={"page_number": page_index + 1},
                ) from error
            os.replace(temporary_path, target_path)
        except OCRLLMError:
            raise
        except (MemoryError, OSError, ValueError) as error:
            raise OutputError(
                "A PDF page could not be rendered to a durable PNG.",
                code="OUTPUT_WRITE_FAILED",
                details={"page_number": page_index + 1},
            ) from error
        except Exception as error:
            raise PDFError(
                "The PDF backend could not render a page.",
                code="PDF_INVALID",
                details={"page_number": page_index + 1},
            ) from error
    except BaseException as error:
        primary_error = error
        raise
    finally:
        cleanup_failed = False
        for native_object in (image, bitmap, page):
            if native_object is not None:
                try:
                    native_object.close()
                except Exception:
                    cleanup_failed = True
        try:
            temporary_path.unlink(missing_ok=True)
        except (OSError, ValueError):
            cleanup_failed = True
        if cleanup_failed:
            if primary_error is None:
                raise PDFError(
                    "The PDF backend could not release one rendered page safely.",
                    code="PDF_INVALID",
                ) from None
            if isinstance(primary_error, OCRLLMError):
                primary_error._add_safe_detail("pdf_page_cleanup_failed", True)


def _make_file_durable(path: Path) -> None:
    with path.open("r+b") as stream:
        stream.flush()
        os.fsync(stream.fileno())
