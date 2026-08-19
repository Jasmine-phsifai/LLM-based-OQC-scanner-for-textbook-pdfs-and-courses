"""
PDF → JPEG 图片渲染（PyMuPDF）。
"""

from __future__ import annotations

import os
import logging
import uuid
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from threading import Event

import fitz
from PIL import Image

from OCRLLM.core.utils import atomic_temp_path, ensure_dir, resolve_workers, sanitize_path_component
from OCRLLM.core.task_runner import CancelledError

logger = logging.getLogger(__name__)


def _pixmap_to_pil(pix: "fitz.Pixmap") -> Image.Image:
    if pix.alpha or pix.colorspace is None or pix.colorspace.n > 3:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    mode = "RGB" if pix.n >= 3 else "L"
    return Image.frombytes(mode, (pix.width, pix.height), pix.samples)


def _render_one_page(
    pdf_path: str,
    page_index: int,
    img_path: str,
    zoom: float,
    max_side: int,
    quality: int,
) -> tuple[int, str]:
    # fitz.Document 不是线程安全对象；每个任务独立打开文档最稳妥。
    doc = fitz.open(pdf_path)
    try:
        page = doc[page_index]
        # 根据页面实际尺寸计算 zoom，使最长边 ≤ max_side，避免二次 resize
        rect = page.rect
        page_long = max(rect.width, rect.height)
        if page_long > 0:
            max_zoom = max_side / page_long
            effective_zoom = min(zoom, max_zoom)
        else:
            effective_zoom = zoom
        mat = fitz.Matrix(effective_zoom, effective_zoom)
        pix = page.get_pixmap(matrix=mat)
        # 中断/进程被杀不能留下截断图片（会被识图提供方静默当成"无法识别"）
        tmp_path = atomic_temp_path(img_path)
        try:
            try:
                pix.save(tmp_path, jpg_quality=quality)
                with Image.open(tmp_path) as check:
                    check.load()
            except Exception as first_err:
                # MuPDF 的 JPEG 流偶发无法被 PIL 解码；改用 PIL 从像素重编码兜底。
                logger.warning(
                    "[PDF2IMG] 第 %d 页 MuPDF 编码校验失败(%s)，改用 PIL 重编码",
                    page_index + 1, first_err,
                )
                img = _pixmap_to_pil(pix)
                img.save(tmp_path, format="JPEG", quality=quality)
                with Image.open(tmp_path) as check:
                    check.load()
            os.replace(tmp_path, img_path)
        except Exception as err:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise RuntimeError(f"第 {page_index + 1} 页渲染失败: {err}") from err
        return page_index, img_path
    finally:
        doc.close()


def pdf_to_images(
    pdf_path: str,
    dpi: int = 200,
    page_range: tuple = None,
    max_side: int = 4096,
    quality: int = 85,
    temp_dir: str = None,
    render_workers: int = 0,
    cancel_event: Event | None = None,
    progress_callback=None,
) -> list[str]:
    """
    将 PDF 每一页渲染为 JPEG。

    Returns:
        生成的图片路径列表（按页码排序）。
    """
    pdf_name = sanitize_path_component(Path(pdf_path).stem)
    run_id = uuid.uuid4().hex[:8]
    output_dir = os.path.join(temp_dir or "temp", "pdf_images", pdf_name, run_id)
    ensure_dir(output_dir)

    meta_doc = fitz.open(pdf_path)
    try:
        total = len(meta_doc)
    finally:
        meta_doc.close()

    logger.info("[PDF2IMG] %s: 共 %d 页, DPI=%d", pdf_path, total, dpi)

    if page_range:
        start, end = page_range
        indices = list(range(max(0, start - 1), min(total, end)))
    else:
        indices = list(range(total))

    zoom = dpi / 72.0
    image_paths = [""] * len(indices)

    workers = resolve_workers(configured=render_workers, task_count=len(indices), hard_cap=8)
    logger.info("[PDF2IMG] 并行渲染: 页数=%d, workers=%d", len(indices), workers)

    # PIL 的解码器注册是惰性且非线程安全的；多线程首次 Image.open 竞态会报
    # "broken data stream"。先在主线程完成注册。
    Image.init()

    if progress_callback:
        progress_callback(0, len(indices))

    ex = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="pdf-render")
    try:
        future_map = {}
        for pos, page_index in enumerate(indices):
            if cancel_event and cancel_event.is_set():
                raise CancelledError("任务已取消")
            img_path = os.path.join(output_dir, f"page_{page_index + 1:04d}.jpg")
            fut = ex.submit(
                _render_one_page,
                pdf_path,
                page_index,
                img_path,
                zoom,
                max_side,
                quality,
            )
            future_map[fut] = pos

        completed = 0
        pending = set(future_map)
        while pending:
            if cancel_event and cancel_event.is_set():
                for fut in pending:
                    fut.cancel()
                raise CancelledError("任务已取消")

            done, pending = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
            if not done:
                continue

            for fut in done:
                pos = future_map[fut]
                _idx, img_path = fut.result()
                image_paths[pos] = img_path
                completed += 1
                if progress_callback:
                    progress_callback(completed, len(indices))
    finally:
        ex.shutdown(wait=False, cancel_futures=True)

    logger.info("[PDF2IMG] 生成 %d 张图片 -> %s", len(image_paths), output_dir)
    return image_paths
