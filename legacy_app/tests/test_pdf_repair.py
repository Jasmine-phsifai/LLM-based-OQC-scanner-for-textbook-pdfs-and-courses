import importlib
from pathlib import Path

import pytest

from OCRLLM.config import AppConfig
from OCRLLM.core.task_runner import ProgressReporter
from OCRLLM.processors.pdf import PDFProcessor


class _ScriptedPDFLLM:
    def __init__(self):
        self.page_calls: list[tuple[int, list[str]]] = []

    def chat_with_images(self, *, prompt, image_paths):
        page = int(prompt.rsplit("=", 1)[-1].split("-", 1)[0])
        self.page_calls.append((page, list(image_paths)))
        if page in (2, 4):
            raise RuntimeError(f"page {page} failed")
        return f"Recognized page {page} content"


def test_pdf_repair_rewrites_partial_range_and_keeps_failures_discoverable(
    tmp_path: Path, monkeypatch
):
    pdf_path = tmp_path / "book.pdf"
    md_path = tmp_path / "book.md"
    pdf_path.write_bytes(b"fake pdf")
    md_path.write_text(
        "Before the failed range\n\n"
        "<!-- 第 1-4 页识别失败: initial provider failure -->\n\n"
        "After the failed range\n",
        encoding="utf-8",
    )
    image_paths = [tmp_path / f"page-{page}.png" for page in range(1, 5)]
    for image_path in image_paths:
        image_path.write_bytes(b"fake image")

    render_calls = []

    def fake_render(_pdf_path, **kwargs):
        render_calls.append(kwargs["page_range"])
        page = kwargs["page_range"][0]
        return [str(image_paths[page - 1])]

    monkeypatch.setattr("OCRLLM.processors.pdf.pdf_to_images", fake_render)
    llm = _ScriptedPDFLLM()
    processor = PDFProcessor.__new__(PDFProcessor)
    processor.cfg = AppConfig().with_updates(
        paths={"output_dir": str(tmp_path), "temp_dir": str(tmp_path)},
    )
    processor.llm = llm
    processor.api_pool = None
    processor.reporter = ProgressReporter()
    processor._report = lambda *_args: None
    processor._check_cancelled = lambda: None
    processor._report_content = lambda *_args: None

    with pytest.raises(RuntimeError, match="修复后仍有 2 页失败"):
        processor.repair(str(pdf_path), str(md_path), prompt_template="page={page_range}")

    content = md_path.read_text(encoding="utf-8")
    assert render_calls == [(1, 1), (2, 2), (3, 3), (4, 4)]
    assert [page for page, _images in llm.page_calls] == [1, 2, 3, 4]
    assert [images[0] for _page, images in llm.page_calls] == [
        str(path) for path in image_paths
    ]
    assert "Recognized page 1 content" in content
    assert "Recognized page 3 content" in content
    assert "Before the failed range" in content
    assert "After the failed range" in content
    page_2_marker = "<!-- 第 2 页识别失败: 修复重试后仍失败 -->"
    page_4_marker = "<!-- 第 4 页识别失败: 修复重试后仍失败 -->"
    assert content.index(page_2_marker) < content.index(page_4_marker)
    assert "第 2, 4 页识别失败" not in content
    assert PDFProcessor.find_failed_pages(str(md_path)) == [2, 4]


def test_pdf_repair_preserves_original_when_atomic_replace_fails(
    tmp_path: Path, monkeypatch
):
    pdf_path = tmp_path / "book.pdf"
    md_path = tmp_path / "book.md"
    image_path = tmp_path / "page-1.png"
    original_markdown = (
        "Before repair\r\n\r\n"
        "<!-- 第 1 页识别失败: initial provider failure -->\r\n\r\n"
        "After repair\r\n"
    ).encode("utf-8")
    pdf_path.write_bytes(b"fake pdf")
    md_path.write_bytes(original_markdown)
    image_path.write_bytes(b"fake image")

    render_calls = []

    def fake_render(_pdf_path, **kwargs):
        render_calls.append(kwargs["page_range"])
        return [str(image_path)]

    def fail_replace(_source, _target):
        raise OSError("injected atomic replace failure")

    monkeypatch.setattr("OCRLLM.processors.pdf.pdf_to_images", fake_render)
    atomic_writer = importlib.import_module("OCRLLM.core.write_text_atomically")
    monkeypatch.setattr(atomic_writer.os, "replace", fail_replace)

    llm = _ScriptedPDFLLM()
    processor = PDFProcessor.__new__(PDFProcessor)
    processor.cfg = AppConfig().with_updates(
        paths={"output_dir": str(tmp_path), "temp_dir": str(tmp_path)},
    )
    processor.llm = llm
    processor.api_pool = None
    processor.reporter = ProgressReporter()
    processor._report = lambda *_args: None
    processor._check_cancelled = lambda: None
    processor._report_content = lambda *_args: None

    with pytest.raises(OSError, match="injected atomic replace failure"):
        processor.repair(str(pdf_path), str(md_path), prompt_template="page={page_range}")

    assert md_path.read_bytes() == original_markdown
    assert list(tmp_path.glob(".ocrllm-text-*.tmp")) == []
    assert render_calls == [(1, 1)]
    assert llm.page_calls == [(1, [str(image_path)])]
