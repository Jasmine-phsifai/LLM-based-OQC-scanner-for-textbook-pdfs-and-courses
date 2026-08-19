"""冷进程并行渲染回归测试。

PIL 解码器注册是惰性且非线程安全的：只有"新解释器 + 多线程同时首次
Image.open"才能触发 broken data stream 竞态。常规测试进程里 PIL 已被
其他用例初始化，永远复现不了，所以必须用子进程。
"""

import os
import subprocess
import sys
from pathlib import Path

import fitz
import pytest

_CHILD_SCRIPT = """
import sys
sys.path.insert(0, {app_root!r})
from OCRLLM.imaging.pdf_renderer import pdf_to_images
from PIL import Image

paths = pdf_to_images({pdf!r}, temp_dir={tmp!r}, render_workers=8)
assert len(paths) == {pages}, f"expected {pages} pages, got {{len(paths)}}"
for p in paths:
    with Image.open(p) as im:
        im.load()
print("RENDER_OK")
"""


@pytest.fixture
def many_page_pdf(tmp_path: Path) -> str:
    pdf = tmp_path / "many_pages.pdf"
    doc = fitz.open()
    for i in range(40):
        page = doc.new_page()
        page.insert_text((72, 72), f"page {i + 1}")
    doc.save(str(pdf))
    doc.close()
    return str(pdf)


def test_parallel_render_in_fresh_interpreter(many_page_pdf, tmp_path):
    app_root = str(Path(__file__).resolve().parents[1])
    script = _CHILD_SCRIPT.format(
        app_root=app_root,
        pdf=many_page_pdf,
        tmp=str(tmp_path / "render_tmp"),
        pages=40,
    )
    env = dict(os.environ, OCRLLM_HOME=str(tmp_path / "home"))
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=300, env=env,
    )
    assert proc.returncode == 0, f"fresh-process render failed:\n{proc.stderr}"
    assert "RENDER_OK" in proc.stdout
