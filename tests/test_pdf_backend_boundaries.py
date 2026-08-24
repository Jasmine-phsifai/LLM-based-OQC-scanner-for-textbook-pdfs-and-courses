"""Focused offline boundaries for the lazy, bounded PDFium layer."""

from __future__ import annotations

import builtins
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from ocrllm import InvalidSource, PDFError
from ocrllm.pdf.calculate_pdf_render_scale import (
    MAX_RENDERED_PAGE_PIXELS,
    MAX_RENDERED_SIDE,
    PDF_RENDER_DPI,
    calculate_pdf_render_scale,
)
from ocrllm.pdf.inspect_pdf import inspect_pdf
from ocrllm.pdf.require_pdfium import require_pdfium
from ocrllm.pdf.snapshot_pdf import MAX_PDF_SOURCE_BYTES, snapshot_pdf


class _FakeDocument:
    def __init__(self, page_sizes: tuple[tuple[float, float], ...]) -> None:
        self._page_sizes = page_sizes
        self.closed = False

    def __len__(self) -> int:
        return len(self._page_sizes)

    def get_page_size(self, page_index: int) -> tuple[float, float]:
        return self._page_sizes[page_index]

    def close(self) -> None:
        self.closed = True


def _install_fake_pdfium(monkeypatch, document_factory) -> None:
    fake_module = SimpleNamespace(
        PYPDFIUM_INFO=SimpleNamespace(api_tag=(5, 11, 0), beta=None),
        PdfDocument=document_factory,
    )
    monkeypatch.setitem(sys.modules, "pypdfium2", fake_module)


def test_require_pdfium_accepts_only_the_tested_api_shape(monkeypatch) -> None:
    _install_fake_pdfium(monkeypatch, lambda _path: object())

    loaded = require_pdfium()

    assert loaded.PYPDFIUM_INFO.api_tag == (5, 11, 0)


def test_require_pdfium_maps_a_missing_optional_dependency(monkeypatch) -> None:
    original_import = builtins.__import__

    def import_without_pdfium(name, *args, **kwargs):
        if name == "pypdfium2":
            raise ImportError("test-only missing PDFium")
        return original_import(name, *args, **kwargs)

    monkeypatch.delitem(sys.modules, "pypdfium2", raising=False)
    monkeypatch.setattr(builtins, "__import__", import_without_pdfium)

    with pytest.raises(PDFError) as captured:
        require_pdfium()

    assert captured.value.code == "PDF_BACKEND_UNAVAILABLE"
    assert captured.value.details["extra"] == "pdf-vision"


def test_inspect_pdf_preserves_page_order_and_closes_document(
    tmp_path: Path,
    monkeypatch,
) -> None:
    document = _FakeDocument(((612.0, 792.0), (792.0, 612.0), (400.0, 400.0)))
    _install_fake_pdfium(monkeypatch, lambda _path: document)

    page_sizes = inspect_pdf(tmp_path / "owned.pdf")

    assert page_sizes == ((612.0, 792.0), (792.0, 612.0), (400.0, 400.0))
    assert document.closed is True


def test_inspect_pdf_maps_password_requirement_and_malformed_input(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class BackendOpenError(Exception):
        def __init__(self, err_code: int) -> None:
            self.err_code = err_code

    for err_code, expected_code in ((4, "PDF_PASSWORD_REQUIRED"), (3, "PDF_INVALID")):
        def fail_open(_path, *, _err_code=err_code):
            raise BackendOpenError(_err_code)

        _install_fake_pdfium(monkeypatch, fail_open)
        with pytest.raises(PDFError) as captured:
            inspect_pdf(tmp_path / "owned.pdf")
        assert captured.value.code == expected_code


def test_snapshot_pdf_rejects_oversized_source_before_copying(tmp_path: Path) -> None:
    source = tmp_path / "oversized.pdf"
    with source.open("wb") as stream:
        stream.truncate(MAX_PDF_SOURCE_BYTES + 1)

    with pytest.raises(InvalidSource) as captured:
        with snapshot_pdf(source, temp_dir=tmp_path / "snapshots"):
            raise AssertionError("oversized PDF unexpectedly yielded a snapshot")

    assert captured.value.code == "SOURCE_TOO_LARGE"
    assert not (tmp_path / "snapshots").exists()


def test_render_scale_respects_dpi_side_and_pixel_ceilings() -> None:
    scale = calculate_pdf_render_scale(612.0, 792.0)

    assert scale <= PDF_RENDER_DPI / 72
    assert 792.0 * scale <= MAX_RENDERED_SIDE
    assert 612.0 * 792.0 * scale * scale <= MAX_RENDERED_PAGE_PIXELS


@pytest.mark.parametrize(
    ("width", "height"),
    ((0.0, 100.0), (100.0, -1.0), (float("inf"), 100.0)),
)
def test_render_scale_rejects_invalid_dimensions(width: float, height: float) -> None:
    with pytest.raises(PDFError) as captured:
        calculate_pdf_render_scale(width, height)

    assert captured.value.code == "PDF_INVALID"
