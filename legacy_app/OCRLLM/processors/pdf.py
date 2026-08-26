"""
PDF 处理器 — 支持 OCR 模式和 LLM 公式识别模式。
"""

from __future__ import annotations

import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import fitz

from OCRLLM.config import AppConfig
from OCRLLM.core.checkpoint import Checkpoint
from OCRLLM.core.incremental_writer import IncrementalMDWriter
from OCRLLM.core.llm_client import LLMClient
from OCRLLM.core.output_quality import failed_placeholder_quality_reason, looks_like_refusal
from OCRLLM.core.provider_selection import (
    uses_google_for_vision,
    visual_allows_high_parallel,
    visual_batch_size,
    visual_parallel_requests,
    visual_request_stagger_seconds,
)
from OCRLLM.core.provider_errors import is_provider_setup_error
from OCRLLM.core.task_runner import CancelledError, ProgressReporter
from OCRLLM.core.progress_tracker import ProgressTracker
from OCRLLM.core.utils import (
    batch_list,
    concat_md_files,
    count_page_headers,
    ensure_dir,
    normalize_page_headers,
    normalize_single_page_markdown,
    resolve_workers,
    sanitize_llm_markdown,
    strip_md_fence,
)
from OCRLLM.imaging.ocr_engine import RapidOCREngine
from OCRLLM.imaging.pdf_renderer import pdf_to_images
from OCRLLM.imaging.scan_detector import is_scanned_pdf
from OCRLLM.imaging.tbpu import run_tbpu
from OCRLLM.processors.base import BaseProcessor
from OCRLLM.core.document_model import SourceType
from OCRLLM import prompts

logger = logging.getLogger(__name__)

# Pattern for failed-page placeholders embedded in output markdown
_FAILED_PAGE_RE = re.compile(
    r"<!--\s*第\s+(\d+)(?:-(\d+))?\s*(?:页识别失败|页逐页识别失败).*?-->",
)


class PDFProcessor(BaseProcessor):
    """PDF → Markdown 处理器。"""

    processor_key = "pdf"
    display_name = "PDF 识别"
    supported_extensions = (".pdf",)
    source_type = SourceType.PDF

    @staticmethod
    def _serialize_page_range(page_range: tuple[int, int] | None) -> list[int] | None:
        return list(page_range) if page_range is not None else None

    @staticmethod
    def _deserialize_page_range(value) -> tuple[int, int] | None:
        if isinstance(value, (list, tuple)) and len(value) == 2:
            return int(value[0]), int(value[1])
        return None

    def _build_checkpoint_extra(
        self,
        page_range: tuple[int, int] | None,
        prompt_template: str,
    ) -> dict:
        page_offset = (page_range[0] - 1) if page_range else 0
        return {
            "page_range": self._serialize_page_range(page_range),
            "page_offset": page_offset,
            "batch_size": self._llm_batch_size(),
            "prompt_template": prompt_template,
        }

    def _llm_batch_size(self) -> int:
        return visual_batch_size(self.cfg)

    def _llm_parallel_requests(self) -> int:
        return visual_parallel_requests(self.cfg)

    def _llm_request_stagger_seconds(self) -> float:
        return visual_request_stagger_seconds(self.cfg)

    def _use_api_pool_for_llm(self) -> bool:
        return (not uses_google_for_vision(self.cfg)) and self.cfg.api.paid_mode and self.api_pool.pool_size > 1

    @classmethod
    def resume_options_from_checkpoint(cls, checkpoint: Checkpoint) -> dict:
        extra = checkpoint.extra or {}
        return {
            "pdf_path": checkpoint.source_path,
            "need_formula": True,
            "output_path": checkpoint.output_path,
            "page_range": cls._deserialize_page_range(extra.get("page_range")),
            "prompt_template": extra.get("prompt_template") or None,
            "resume": True,
        }

    def process(
        self,
        pdf_path: str,
        need_formula: bool = False,
        output_path: str = None,
        page_range: tuple = None,
        prompt_template: str = None,
        resume: bool = False,
    ) -> str:
        """处理 PDF 文件并生成 Markdown。

        Args:
            pdf_path: PDF 文件路径。
            need_formula: 是否启用 LLM 公式识别模式。
            output_path: 输出路径，None 则自动生成。
            page_range: 页码范围 (start, end)，None 表示全部。
            prompt_template: 自定义提示词模板。
            resume: 是否尝试断点续传。

        Returns:
            输出文件路径。
        """
        pdf_name = Path(pdf_path).stem
        if output_path is None:
            output_path = os.path.join(ensure_dir(self.cfg.paths.output_dir), f"{pdf_name}_识别.md")

        if page_range is not None:
            if len(page_range) != 2 or page_range[0] < 1 or page_range[0] > page_range[1]:
                raise ValueError(
                    f"page_range 无效: {page_range}，要求 (start, end) 且 1 <= start <= end"
                )

        scanned = is_scanned_pdf(pdf_path)
        logger.info("[PDF] 文件=%s, 扫描型=%s, 公式=%s, 页码=%s", pdf_name, scanned, need_formula, page_range)

        if scanned and not need_formula:
            logger.warning("[PDF] 检测到扫描型PDF，建议启用大模型公式识别模式以获得更好效果")
            self._report(0, 1, "⚠ 检测到扫描型PDF，当前为OCR模式，建议开启公式识别")

        if need_formula:
            return self._process_with_llm(pdf_path, output_path, page_range, prompt_template, resume)
        return self._process_with_ocr(pdf_path, output_path, page_range)

    def _process_with_ocr(self, pdf_path: str, output_path: str, page_range: tuple = None) -> str:
        doc = fitz.open(pdf_path)
        try:
            total = len(doc)
            start_page = max(0, page_range[0] - 1) if page_range else 0
            end_page = min(total, page_range[1]) if page_range else total
            pages = list(range(start_page, end_page))

            self._report(0, len(pages), "初始化 RapidOCR 引擎...")
            ocr = RapidOCREngine(max_side_len=4096)
            md_pages = []

            for idx, page_index in enumerate(pages):
                try:
                    page = doc[page_index]
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    img_bytes = pix.tobytes("png")

                    self._report(idx + 1, len(pages), f"OCR 识别第 {page_index + 1}/{total} 页")

                    blocks = ocr.run_bytes(img_bytes)
                    if not blocks:
                        md_pages.append(f"<!-- meta:page number={page_index + 1} -->\n\n")
                        continue

                    ordered = run_tbpu(blocks)
                    text = "".join(block["text"] + block.get("end", "\n") for block in ordered)
                    md_pages.append(f"<!-- meta:page number={page_index + 1} -->\n\n{text.strip()}")
                    self._report_content(text.strip(), f"OCR 识别 — 第 {page_index + 1} 页")
                except (RuntimeError, OSError, ValueError, TypeError) as e:
                    logger.error("[PDF] 第 %d 页 OCR 失败: %s", page_index + 1, e)
                    safe_err = str(e).replace("--", "\u2014")
                    md_pages.append(f"<!-- meta:page number={page_index + 1} -->\n\n<!-- OCR 失败: {safe_err} -->\n")
        finally:
            doc.close()

        ensure_dir(os.path.dirname(output_path))
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(md_pages))
        self._raise_if_failed_output_too_short(output_path, len(pages))
        logger.info("[PDF] RapidOCR 识别完成 -> %s", output_path)
        return output_path

    def _process_with_llm(
        self,
        pdf_path: str,
        output_path: str,
        page_range: tuple = None,
        prompt_template: str = None,
        resume: bool = False,
    ) -> str:
        prompt_template = prompt_template or prompts.PDF_FORMULA
        checkpoint_extra = self._build_checkpoint_extra(page_range, prompt_template)

        with fitz.open(pdf_path) as meta_doc:
            total_doc_pages = len(meta_doc)
        render_total = max(0, min(total_doc_pages, page_range[1]) - max(0, page_range[0] - 1)) if page_range else total_doc_pages

        self.tracker.start_task(
            "pdf",
            total_items=render_total,
            phase_weights={"render": 0.15, "llm": 0.85},
        )
        self.tracker.start_phase("render", "PDF 转换为图片", render_total)
        self._report(0, 1, "PDF 转换为图片中...")

        image_paths = pdf_to_images(
            pdf_path,
            dpi=self.cfg.processing.pdf_dpi,
            page_range=page_range,
            max_side=self.cfg.processing.image_max_side,
            quality=self.cfg.processing.image_quality,
            temp_dir=self.cfg.paths.temp_dir,
            render_workers=self.cfg.concurrency.pdf_render_workers,
            cancel_event=self.reporter.cancel_event,
            progress_callback=lambda current, total: self.tracker.update_phase(
                "render",
                current,
                f"PDF 转换为图片: {current}/{total}",
                total=total,
            ),
        )
        total_pages = len(image_paths)
        self.tracker.finish_phase("render")
        logger.info("[PDF] 共 %d 张图片待识别", total_pages)

        cancelled = False
        try:
            batch_size = self._llm_batch_size()
            batches = batch_list(image_paths, batch_size)
            page_offset = (page_range[0] - 1) if page_range else 0

            if not batches:
                concat_md_files([], output_path)
                return output_path

            checkpoint = None
            restored_slots = {}
            skip_batches = set()
            if resume:
                checkpoint = self.checkpoint_mgr.load("pdf", pdf_path)
                if checkpoint and checkpoint.is_compatible(
                    total_items=len(batches),
                    output_path=output_path,
                    expected_extra=checkpoint_extra,
                ):
                    existing_output = ""
                    if os.path.exists(output_path):
                        existing_output = Path(output_path).read_text(encoding="utf-8")
                    restored_slots = self._restore_completed_slots(
                        existing_output,
                        checkpoint.completed_indices,
                        batches,
                        page_offset,
                    )
                    skip_batches = set(restored_slots)
                    logger.info("[PDF] 断点续传: 跳过 %d/%d 个已完成批次", len(skip_batches), len(batches))
                    missing_batches = checkpoint.completed_indices - skip_batches
                    if missing_batches:
                        logger.warning("[PDF] %d 个已完成批次缺少可恢复内容，将重新识别", len(missing_batches))
                    self._report(
                        0,
                        1,
                        f"断点续传: 从第 {len(skip_batches) + 1} 批继续 (已完成 {len(skip_batches)}/{len(batches)})",
                    )
                else:
                    if checkpoint is not None:
                        logger.warning("[PDF] 检查点与当前任务参数不兼容，忽略旧检查点")
                        self._report(0, 1, "⚠ 检查点与当前参数（提示词/批次/页码）不兼容，将重新识别")
                    checkpoint = None

            if checkpoint is None:
                checkpoint = Checkpoint(
                    task_type="pdf",
                    source_path=pdf_path,
                    output_path=output_path,
                    total_items=len(batches),
                    extra=checkpoint_extra,
                )
            # 立即落盘：即使全部批次失败或进程中断，也要留下可续传入口
            self.checkpoint_mgr.save(checkpoint)

            self.tracker.set_total(total_pages)
            self.tracker.start_phase("llm", "大模型识别", len(batches))

            pending_count = len(batches) - len(skip_batches)
            logger.info(
                "[PDF] 识别队列: %d 批次待处理, %d 批次已完成 (每批 %d 页)",
                pending_count,
                len(skip_batches),
                batch_size,
            )

            writer = IncrementalMDWriter(
                output_path, total_slots=len(batches),
                truncate=not bool(restored_slots),
            )
            if restored_slots:
                writer.seed_slots(restored_slots)

            restored_pages = sum(len(batches[idx]) for idx in skip_batches)
            if restored_pages:
                self.tracker.increment_completed(restored_pages)
                self.tracker.update_phase("llm", len(skip_batches), "已恢复断点内容")

            if pending_count <= 0:
                writer.finalize()
                self.checkpoint_mgr.remove("pdf", pdf_path)
                logger.info("[PDF] 断点续传直接恢复完成 -> %s", output_path)
                return output_path

            high_parallel_provider = visual_allows_high_parallel(self.cfg)
            base_workers = resolve_workers(self._llm_parallel_requests(), pending_count, hard_cap=64 if high_parallel_provider else 8)
            if self._use_api_pool_for_llm() and pending_count > base_workers:
                workers = min(self.api_pool.max_parallel, pending_count, base_workers * self.api_pool.pool_size)
                logger.info("[PDF] 付费模式: 并行度提升 %d → %d (API 池 %d 个 key)", base_workers, workers, self.api_pool.pool_size)
            else:
                workers = base_workers

            logger.info("[PDF] 并行识别批次: 批次数=%d, workers=%d, 待处理=%d", len(batches), workers, pending_count)

            stagger = self._llm_request_stagger_seconds() if pending_count > 4 else 0
            self.tracker.update_queue(max(0, pending_count - workers), min(workers, pending_count))

            executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="pdf-llm")
            future_map = {}
            failed_page_ranges: list[str] = []
            try:
                for batch_idx, batch in enumerate(batches):
                    self._check_cancelled()
                    if batch_idx in skip_batches:
                        continue
                    future = executor.submit(
                        self._process_llm_batch_tracked,
                        batch_idx,
                        batch,
                        page_offset,
                        prompt_template,
                        writer,
                        checkpoint,
                    )
                    future_map[future] = batch_idx
                    if stagger and batch_idx < len(batches) - 1:
                        self._sleep(stagger)

                done = len(skip_batches)
                successful_batches = len(skip_batches)
                for future in self._iter_completed_futures(set(future_map)):
                    batch_idx = future_map.pop(future, None)
                    if batch_idx is None:
                        continue
                    done += 1
                    try:
                        idx, page_str, result, success = future.result()
                        if success:
                            successful_batches += 1
                        else:
                            failed_pages = re.findall(r"第\s+(\d+(?:-\d+)?)\s+页识别失败", result)
                            failed_page_ranges.extend(failed_pages or [page_str])
                        self.tracker.update_phase("llm", done, f"完成第 {page_str} 页")
                        self.tracker.increment_completed(len(batches[idx]))
                        self._report(done, len(batches), f"完成第 {page_str} 页批次 ({done}/{len(batches)})")
                        self._report_content(result, f"大模型识别 — 第 {page_str} 页")

                        remaining = len(batches) - done
                        running = min(workers, remaining)
                        self.tracker.update_queue(max(0, remaining - running), running)
                    except CancelledError:
                        raise
                    except Exception as e:
                        if is_provider_setup_error(e):
                            logger.error("[PDF] Provider 环境错误，中止大模型识别: %s", e)
                            raise
                        logger.error("[PDF] 批次 %d 异常: %s", batch_idx, e)
                        self.tracker.increment_error()
                        b_start = page_offset + batch_idx * batch_size + 1
                        b_end = b_start + len(batches[batch_idx]) - 1
                        failed_page_ranges.append(f"{b_start}-{b_end}" if b_end > b_start else str(b_start))
            finally:
                self._cancel_futures(future_map)
                executor.shutdown(wait=True, cancel_futures=True)

            # --- Retry pass for failed batches ---
            failed_batch_indices = self._collect_failed_batch_indices(
                failed_page_ranges, batches, page_offset, batch_size
            )
            if failed_batch_indices and successful_batches > 0:
                logger.info("[PDF] 开始重试 %d 个失败批次 (等待 10s 后重试)", len(failed_batch_indices))
                self._report(0, 1, f"⏳ 等待后重试 {len(failed_batch_indices)} 个失败批次...")
                self._sleep(10)
                retry_failed_ranges: list[str] = []
                retry_executor = ThreadPoolExecutor(
                    max_workers=max(1, workers // 2), thread_name_prefix="pdf-retry"
                )
                retry_future_map = {}
                try:
                    for batch_idx in failed_batch_indices:
                        self._check_cancelled()
                        future = retry_executor.submit(
                            self._process_llm_batch_tracked,
                            batch_idx,
                            batches[batch_idx],
                            page_offset,
                            prompt_template,
                            writer,
                            checkpoint,
                        )
                        retry_future_map[future] = batch_idx
                        if stagger:
                            self._sleep(stagger * 2)

                    for future in self._iter_completed_futures(set(retry_future_map)):
                        batch_idx = retry_future_map.pop(future, None)
                        if batch_idx is None:
                            continue
                        try:
                            idx, page_str, result, success = future.result()
                            if success:
                                successful_batches += 1
                                # Remove from failed ranges on success
                                failed_page_ranges = [
                                    r for r in failed_page_ranges if r != page_str
                                ]
                            else:
                                retry_failed_ranges.append(page_str)
                            self._report(0, 1, f"重试完成第 {page_str} 页 ({'✓' if success else '✗'})")
                        except CancelledError:
                            raise
                        except Exception as e:
                            if is_provider_setup_error(e):
                                raise
                            logger.error("[PDF] 重试批次 %d 异常: %s", batch_idx, e)
                finally:
                    self._cancel_futures(retry_future_map)
                    retry_executor.shutdown(wait=True, cancel_futures=True)
                # Update failed_page_ranges to only contain still-failing pages
                if retry_failed_ranges:
                    failed_page_ranges = retry_failed_ranges
                else:
                    failed_page_ranges = []

            self.tracker.finish_phase("llm")
            writer.finalize()
            if successful_batches == 0:
                raise RuntimeError(f"PDF 大模型识别全部 {len(batches)} 个批次失败，输出文件只包含错误信息: {output_path}")
            self._raise_if_failed_output_too_short(output_path, total_pages)
            if failed_page_ranges:
                failed_ranges = ", ".join(dict.fromkeys(failed_page_ranges))
                raise RuntimeError(f"PDF 输出包含识别失败，失败页范围: {failed_ranges}: {output_path}")
            self.checkpoint_mgr.remove("pdf", pdf_path)

            bottleneck = self.tracker.get_bottleneck_report()
            if bottleneck:
                logger.info("[PDF] %s", bottleneck)

            logger.info("[PDF] 大模型识别完成 -> %s", output_path)
            return output_path
        except CancelledError:
            cancelled = True
            logger.info("[PDF] 任务已取消，保留临时图片以便调试")
            raise
        finally:
            if not cancelled:
                self._cleanup_images(image_paths)

    def _process_llm_batch_tracked(
        self,
        batch_idx: int,
        batch: list[str],
        page_offset: int,
        prompt_template: str,
        writer: IncrementalMDWriter,
        checkpoint: Checkpoint,
    ) -> tuple[int, str, str, bool]:
        self._check_cancelled()
        start_page = page_offset + batch_idx * self._llm_batch_size() + 1
        end_page = start_page + len(batch) - 1
        page_str = f"{start_page}-{end_page}"
        prompt = prompt_template.format(page_range=page_str)

        if self._use_api_pool_for_llm():
            with self.api_pool.get_client() as client:
                result, success = self._do_batch_llm(client, prompt, batch, page_str, start_page, prompt_template)
        else:
            result, success = self._do_batch_llm(self.llm, prompt, batch, page_str, start_page, prompt_template)

        self._check_cancelled()
        writer.write_slot(batch_idx, result)
        if success:
            self.checkpoint_mgr.save_incremental(checkpoint, batch_idx, "")
        else:
            logger.warning("[PDF] 批次 %s 未成功完成，不写入检查点", page_str)
        return batch_idx, page_str, result, success

    def _do_batch_llm(
        self,
        client: LLMClient,
        prompt: str,
        batch: list[str],
        page_str: str,
        start_page: int,
        prompt_template: str,
    ) -> tuple[str, bool]:
        try:
            result = client.chat_with_images(prompt=prompt, image_paths=batch)
            result = strip_md_fence(result)
            result = sanitize_llm_markdown(result)
            result = normalize_page_headers(result, start_page, len(batch))

            if count_page_headers(result) != len(batch):
                logger.warning("[PDF] 批次 %s 页标题异常，回退逐页识别", page_str)
                return self._rerun_per_page(batch, start_page, prompt_template)

            if looks_like_refusal(result):
                logger.warning("[PDF] 批次 %s 疑似模型拒识（响应非空但为拒绝文本），回退逐页识别", page_str)
                return self._rerun_per_page(batch, start_page, prompt_template)

            return result, True
        except CancelledError:
            raise
        except Exception as e:
            if is_provider_setup_error(e):
                raise
            logger.error("[PDF] 批次 %s 失败: %s", page_str, e)
            safe_err = str(e).replace("--", "\u2014")
            return f"\n\n<!-- 第 {page_str} 页识别失败: {safe_err} -->\n\n", False

    def _restore_completed_slots(
        self,
        existing_content: str,
        completed_batches: set[int],
        batches: list,
        page_offset: int,
    ) -> dict[int, str]:
        try:
            restored = {}
            # 支持新格式 <!-- meta:page number=X --> 和旧格式 # Page X
            page_sections = re.split(
                r"(?=^<!--\s*meta:page\s+number=\d+\s*-->)|(?=^# Page \d+)",
                existing_content,
                flags=re.MULTILINE,
            )
            page_map = {}
            for section in page_sections:
                m = re.match(r"^<!--\s*meta:page\s+number=(\d+)\s*-->", section)
                if not m:
                    m = re.match(r"^# Page (\d+)", section)
                if m:
                    page_map[int(m.group(1))] = section.strip()

            for batch_idx in sorted(completed_batches):
                start_page = page_offset + batch_idx * self._llm_batch_size() + 1
                end_page = start_page + len(batches[batch_idx]) - 1
                parts = []
                for page_num in range(start_page, end_page + 1):
                    part = page_map.get(page_num)
                    if not part:
                        parts = []
                        break
                    parts.append(part)
                if parts:
                    restored[batch_idx] = "\n\n".join(parts)

            logger.info("[PDF] 恢复了 %d 个已完成批次的内容", len(restored))
            return restored
        except (OSError, ValueError, IndexError) as e:
            logger.warning("[PDF] 无法恢复旧内容: %s", e)
            return {}

    def _rerun_per_page(self, batch: list[str], start_page: int, prompt_template: str) -> tuple[str, bool]:
        high_parallel_provider = visual_allows_high_parallel(self.cfg)
        workers = resolve_workers(self._llm_parallel_requests(), len(batch), hard_cap=64 if high_parallel_provider else 8)
        parts = [""] * len(batch)
        success = True

        def _one(idx: int, img_path: str) -> tuple[int, str, bool]:
            page_num = start_page + idx
            try:
                prompt = prompt_template.format(page_range=f"{page_num}-{page_num}")
                if self._use_api_pool_for_llm():
                    with self.api_pool.get_client() as client:
                        result = client.chat_with_images(prompt=prompt, image_paths=[img_path])
                else:
                    result = self.llm.chat_with_images(prompt=prompt, image_paths=[img_path])
                result = strip_md_fence(result)
                result = sanitize_llm_markdown(result)
                result = normalize_single_page_markdown(result, page_num)
                if looks_like_refusal(result):
                    logger.error("[PDF] 第 %d 页模型拒识（非空但非识别内容）", page_num)
                    safe_err = "模型拒识：" + result.strip().splitlines()[0][:80]
                    return idx, f"\n\n<!-- 第 {page_num} 页识别失败: {safe_err} -->\n\n", False
                return idx, result, True
            except CancelledError:
                raise
            except Exception as e:
                if is_provider_setup_error(e):
                    raise
                logger.error("[PDF] 第 %d 页逐页识别失败: %s", page_num, e)
                safe_err = str(e).replace("--", "\u2014")
                return idx, f"\n\n<!-- 第 {page_num} 页识别失败: {safe_err} -->\n\n", False

        executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="pdf-rerun")
        future_map = {}
        try:
            for idx, path in enumerate(batch):
                self._check_cancelled()
                future = executor.submit(_one, idx, path)
                future_map[future] = idx

            for future in self._iter_completed_futures(set(future_map)):
                future_map.pop(future, None)
                idx, text, ok = future.result()
                parts[idx] = text
                success = success and ok
        finally:
            self._cancel_futures(future_map)
            executor.shutdown(wait=True, cancel_futures=True)

        return "\n\n".join(parts), success

    @staticmethod
    def _collect_failed_batch_indices(
        failed_page_ranges: list[str],
        batches: list,
        page_offset: int,
        batch_size: int,
    ) -> list[int]:
        """Map failed page-range strings back to batch indices for retry."""
        indices = set()
        for r in failed_page_ranges:
            m = re.match(r"(\d+)(?:-(\d+))?", r)
            if not m:
                continue
            start = int(m.group(1))
            idx = max(0, (start - 1 - page_offset) // batch_size)
            if idx < len(batches):
                indices.add(idx)
        return sorted(indices)

    @staticmethod
    def _raise_if_failed_output_too_short(output_path: str, expected_pages: int) -> None:
        try:
            content = Path(output_path).read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"PDF 输出质量检查失败，无法读取输出文件: {output_path}") from exc
        reason = failed_placeholder_quality_reason(
            content,
            expected_units=expected_pages,
            unit_name="页",
        )
        if reason:
            raise RuntimeError(f"PDF 输出包含识别失败且有效正文过少: {reason}: {output_path}")

    @staticmethod
    def _cleanup_images(paths: list[str]):
        parent_dirs = set()
        for path in paths:
            try:
                parent_dirs.add(str(Path(path).parent))
                Path(path).unlink(missing_ok=True)
            except Exception:
                pass
        for directory in parent_dirs:
            try:
                Path(directory).rmdir()
            except Exception:
                pass

    # ---- Repair mode: re-recognize only failed pages in existing output ----

    @staticmethod
    def find_failed_pages(md_path: str) -> list[int]:
        """Return 1-based page numbers that have failure placeholders."""
        try:
            text = Path(md_path).read_text(encoding="utf-8")
        except OSError:
            return []
        pages: set[int] = set()
        for m in _FAILED_PAGE_RE.finditer(text):
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else start
            pages.update(range(start, end + 1))
        return sorted(pages)

    def repair(
        self,
        pdf_path: str,
        md_path: str,
        prompt_template: str = None,
    ) -> str:
        """Re-recognize only the failed pages in an existing output markdown.

        Renders only the needed pages from the PDF, recognizes them, and
        replaces the failure placeholders in-place.  Already-recognized pages
        are untouched.

        Returns:
            The md_path, or raises if any pages still fail after repair.
        """
        failed_pages = self.find_failed_pages(md_path)
        if not failed_pages:
            logger.info("[PDF-REPAIR] 没有找到识别失败的页: %s", md_path)
            return md_path

        prompt_template = prompt_template or prompts.PDF_FORMULA
        logger.info("[PDF-REPAIR] 需要修复 %d 页: %s", len(failed_pages), failed_pages)
        self._report(0, len(failed_pages), f"修复 {len(failed_pages)} 个失败页...")

        # Render only the pages we need
        image_map: dict[int, str] = {}
        try:
            for idx, page_num in enumerate(failed_pages):
                self._check_cancelled()
                self._report(idx, len(failed_pages), f"渲染第 {page_num} 页...")
                paths = pdf_to_images(
                    pdf_path,
                    dpi=self.cfg.processing.pdf_dpi,
                    page_range=(page_num, page_num),
                    max_side=self.cfg.processing.image_max_side,
                    quality=self.cfg.processing.image_quality,
                    temp_dir=self.cfg.paths.temp_dir,
                    render_workers=1,
                    cancel_event=self.reporter.cancel_event,
                )
                if paths:
                    image_map[page_num] = paths[0]

            # Recognize each failed page individually
            results: dict[int, str] = {}
            still_failed: list[int] = []
            for idx, page_num in enumerate(failed_pages):
                self._check_cancelled()
                img = image_map.get(page_num)
                if not img:
                    still_failed.append(page_num)
                    continue
                self._report(idx + 1, len(failed_pages), f"识别第 {page_num} 页 ({idx + 1}/{len(failed_pages)})")
                prompt = prompt_template.format(page_range=f"{page_num}-{page_num}")
                try:
                    if self._use_api_pool_for_llm():
                        with self.api_pool.get_client() as client:
                            text = client.chat_with_images(prompt=prompt, image_paths=[img])
                    else:
                        text = self.llm.chat_with_images(prompt=prompt, image_paths=[img])
                    text = strip_md_fence(text)
                    text = sanitize_llm_markdown(text)
                    text = normalize_single_page_markdown(text, page_num)
                    if looks_like_refusal(text):
                        logger.warning("[PDF-REPAIR] 第 %d 页模型拒识", page_num)
                        still_failed.append(page_num)
                        continue
                    results[page_num] = text
                    self._report_content(text, f"修复识别 — 第 {page_num} 页")
                except CancelledError:
                    raise
                except Exception as e:
                    if is_provider_setup_error(e):
                        raise
                    logger.error("[PDF-REPAIR] 第 %d 页识别失败: %s", page_num, e)
                    still_failed.append(page_num)
        finally:
            self._cleanup_images(list(image_map.values()))

        if not results:
            raise RuntimeError(f"PDF 修复识别全部 {len(failed_pages)} 页失败")

        # Replace failure placeholders in the markdown.
        # Placeholders can be single-page (第 5 页) or range (第 9-16 页).
        # For ranges, assemble all successfully-repaired pages into one block.
        content = Path(md_path).read_text(encoding="utf-8")
        for m in _FAILED_PAGE_RE.finditer(content):
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else start
            range_pages = list(range(start, end + 1))
            repaired_parts = [results[p] for p in range_pages if p in results]
            if not repaired_parts:
                continue
            replacement = "\n\n".join(repaired_parts)
            # Keep one grammar-valid marker per missing page so the next repair
            # pass can discover every remaining failure.
            still_missing = [p for p in range_pages if p not in results]
            for page_num in still_missing:
                replacement += (
                    f"\n\n<!-- 第 {page_num} 页识别失败: 修复重试后仍失败 -->\n\n"
                )
            content = content.replace(m.group(0), "\n\n" + replacement + "\n\n", 1)

        Path(md_path).write_text(content, encoding="utf-8")
        logger.info(
            "[PDF-REPAIR] 修复完成: %d/%d 页成功, %d 页仍失败 -> %s",
            len(results), len(failed_pages), len(still_failed), md_path,
        )
        if still_failed:
            raise RuntimeError(f"PDF 修复后仍有 {len(still_failed)} 页失败: {still_failed}: {md_path}")
        return md_path
