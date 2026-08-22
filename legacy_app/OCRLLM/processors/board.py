"""
板书/截图识别处理器 — 上下文连续多模态请求。
"""

from __future__ import annotations

import os
import logging
import re
from pathlib import Path
from typing import Optional

from OCRLLM.processors.base import BaseProcessor
from OCRLLM.core.document_model import SourceType
from OCRLLM.core.utils import (
    batch_list, concat_md_files, ensure_dir,
    sort_files_by_time, resize_image_if_needed, strip_md_fence,
)
from OCRLLM.core.output_quality import failed_placeholder_quality_reason, looks_like_refusal
from OCRLLM.imaging.preprocess import ImagePreprocessor
from OCRLLM import prompts

logger = logging.getLogger(__name__)

_BOARD_HISTORY_MESSAGES = 8

_FAILED_BATCH_RE = re.compile(
    r"<!--\s*批次\s+(\d+)\s+\(([^)]*)\)\s+识别失败:\s*.*?-->",
)


def _default_board_output_path(output_dir: str, image_paths: list[str]) -> str:
    stems = [Path(p).stem for p in image_paths]
    parent_names = {Path(p).parent.name for p in image_paths if Path(p).parent.name}
    common_prefix = os.path.commonprefix(stems).strip(" _-.")

    if len(stems) == 1:
        base_name = stems[0]
    elif common_prefix and len(common_prefix) >= 3:
        base_name = common_prefix
    elif len(parent_names) == 1:
        base_name = next(iter(parent_names))
    else:
        base_name = f"板书_{len(stems)}张"

    return os.path.join(ensure_dir(output_dir), f"{base_name}_板书识别.md")


class BoardProcessor(BaseProcessor):
    """
    板书/截图 → Markdown 处理器。

    用法:
        proc = BoardProcessor()
        md_path = proc.process(["img1.jpg", "img2.jpg"])
    """

    processor_key = "board"
    display_name = "板书/截图识别"
    supported_extensions = (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".heic", ".heif", ".tif", ".tiff")
    source_type = SourceType.BOARD

    def process(
        self,
        image_paths: list[str],
        output_path: str = None,
        manual_quads: Optional[dict] = None,
        skip_preprocess: bool = False,
        prompt_template: str = None,
    ) -> str:
        """识别板书/截图并生成 Markdown。

        Args:
            image_paths: 图片文件路径列表。
            output_path: 输出 Markdown 路径，None 则自动生成。
            manual_quads: 各图片手动裁剪四边形。
            skip_preprocess: 跳过自动裁剪预处理。
            prompt_template: 自定义识别提示词。

        Returns:
            输出文件路径。
        """
        prompt_template = prompt_template or prompts.BOARD
        sorted_paths = sort_files_by_time(image_paths)

        if output_path is None:
            output_path = _default_board_output_path(self.cfg.paths.output_dir, sorted_paths)
        logger.info("[BOARD] 共 %d 张图片", len(sorted_paths))

        preprocessor = ImagePreprocessor(self.cfg)
        if not skip_preprocess:
            self._report(0, len(sorted_paths), "图片预处理中...")
            processed_paths = preprocessor.process_batch(sorted_paths, manual_quads)
            for p in processed_paths:
                self._check_cancelled()
                resize_image_if_needed(
                    p,
                    self.cfg.processing.image_max_side,
                    self.cfg.processing.image_quality,
                )
        else:
            resize_dir = ensure_dir(os.path.join(self.cfg.paths.temp_dir, "board_resized"))
            processed_paths = []
            for idx, src in enumerate(sorted_paths):
                self._check_cancelled()
                resized_path = os.path.join(resize_dir, f"{idx:04d}_{Path(src).name}")
                processed_paths.append(
                    resize_image_if_needed(
                        src,
                        self.cfg.processing.image_max_side,
                        self.cfg.processing.image_quality,
                        output_path=resized_path,
                    )
                )

        batches = batch_list(
            list(zip(sorted_paths, processed_paths)), self.cfg.processing.batch_size
        )
        md_parts = []
        history = []
        successful_batches = 0
        failed_batches: list[int] = []

        for batch_idx, batch in enumerate(batches):
            self._check_cancelled()
            orig_paths, proc_paths = zip(*batch)
            names = [Path(p).name for p in orig_paths]
            names_str = ", ".join(names)

            self._report(
                batch_idx + 1, len(batches),
                f"识别第 {batch_idx + 1} 批 ({len(batch)} 张: {names_str})"
            )

            prompt = prompt_template.format(image_names=names_str)
            try:
                trimmed_history = history[-_BOARD_HISTORY_MESSAGES:]
                result = self.llm.chat_with_images_contextual(
                    prompt=prompt, image_paths=list(proc_paths), history=trimmed_history,
                )
                result = strip_md_fence(result)
                if looks_like_refusal(result):
                    raise RuntimeError("模型拒识：" + result.strip().splitlines()[0][:80])
                md_parts.append(result)
                successful_batches += 1
                self._report_content(result, f"板书识别 — 第 {batch_idx + 1} 批")

                # 只保留 assistant 的文本输出作为上下文摘要，不伪造图片历史
                if len(history) > _BOARD_HISTORY_MESSAGES - 2:
                    history = history[-(_BOARD_HISTORY_MESSAGES - 2):]
                history.extend([
                    {"role": "user", "content": f"以上是第 {batch_idx + 1} 批（{names_str}）的板书图片，请继续识别下一批。"},
                    {"role": "assistant", "content": result},
                ])
            except Exception as e:
                logger.error("[BOARD] 批次 %d 失败: %s", batch_idx + 1, e)
                safe_err = str(e).replace("--", "\u2014")
                md_parts.append(f"\n\n<!-- 批次 {batch_idx + 1} ({names_str}) 识别失败: {safe_err} -->\n\n")
                failed_batches.append(batch_idx + 1)

        concat_md_files(md_parts, output_path)
        if batches and successful_batches == 0:
            raise RuntimeError(f"板书识别全部 {len(batches)} 个批次失败，输出文件只包含错误信息: {output_path}")
        reason = failed_placeholder_quality_reason(
            "\n\n".join(md_parts), expected_units=len(batches), unit_name="批",
        )
        if reason:
            raise RuntimeError(f"板书识别输出包含识别失败且有效正文过少: {reason}: {output_path}")
        if failed_batches:
            failed = ", ".join(str(batch) for batch in failed_batches)
            raise RuntimeError(f"板书识别输出包含识别失败，失败批次: {failed}: {output_path}")
        logger.info("[BOARD] 板书识别完成 -> %s", output_path)
        return output_path

    @staticmethod
    def find_failed_batches(md_path: str) -> list[tuple[int, list[str]]]:
        """Return (1-based batch index, image names list) for failed batches."""
        try:
            text = Path(md_path).read_text(encoding="utf-8")
        except OSError:
            return []
        results: list[tuple[int, list[str]]] = []
        for m in _FAILED_BATCH_RE.finditer(text):
            idx = int(m.group(1))
            names = [n.strip() for n in m.group(2).split(",") if n.strip()]
            results.append((idx, names))
        return results

    def repair(
        self,
        image_paths: list[str],
        md_path: str,
        skip_preprocess: bool = False,
        prompt_template: str = None,
    ) -> str:
        """Re-recognize failed batches in an existing board MD.

        Uses the original image files to re-process only the failed batches.
        Returns md_path, or raises on total/partial failure.
        """
        failed = self.find_failed_batches(md_path)
        if not failed:
            logger.info("[BOARD-REPAIR] 没有发现识别失败的批次: %s", md_path)
            return md_path

        prompt_template = prompt_template or prompts.BOARD
        # Build name → path map from the original images
        name_to_path = {Path(p).name: p for p in image_paths}

        total = len(failed)
        logger.info("[BOARD-REPAIR] 需要修复 %d 个批次", total)
        self._report(0, total, f"修复 {total} 个失败批次...")

        results: dict[int, str] = {}  # batch index → recognized text
        still_failed: list[int] = []

        preprocessor = ImagePreprocessor(self.cfg)

        for order, (batch_idx, names) in enumerate(failed):
            self._check_cancelled()
            batch_paths = [name_to_path[n] for n in names if n in name_to_path]
            if not batch_paths:
                still_failed.append(batch_idx)
                continue

            self._report(order + 1, total, f"识别批次 {batch_idx} ({order + 1}/{total})")
            names_str = ", ".join(names)
            prompt = prompt_template.format(image_names=names_str)

            # Preprocess
            if not skip_preprocess:
                proc_paths = preprocessor.process_batch(batch_paths, None)
                for p in proc_paths:
                    resize_image_if_needed(
                        p, self.cfg.processing.image_max_side, self.cfg.processing.image_quality,
                    )
            else:
                proc_paths = batch_paths

            try:
                result = self.llm.chat_with_images(prompt=prompt, image_paths=proc_paths)
                text = strip_md_fence(result)
                if looks_like_refusal(text):
                    raise RuntimeError("模型拒识")
                results[batch_idx] = text
                self._report_content(text, f"修复识别 — 批次 {batch_idx}")
            except Exception as e:
                logger.error("[BOARD-REPAIR] 批次 %d 失败: %s", batch_idx, e)
                still_failed.append(batch_idx)

        if not results:
            raise RuntimeError(f"板书修复全部 {total} 个批次失败")

        # Replace placeholders in MD
        content = Path(md_path).read_text(encoding="utf-8")
        for batch_idx, text in results.items():
            pattern = re.compile(
                r"\s*<!--\s*批次\s+" + str(batch_idx) + r"\s+\([^)]*\)\s+识别失败:.*?-->\s*",
            )
            content = pattern.sub("\n\n" + text + "\n\n", content, count=1)

        Path(md_path).write_text(content, encoding="utf-8")
        logger.info(
            "[BOARD-REPAIR] 修复完成: %d/%d 批次成功, %d 批次仍失败 -> %s",
            len(results), total, len(still_failed), md_path,
        )
        if still_failed:
            raise RuntimeError(
                f"板书修复后仍有 {len(still_failed)} 个批次失败: {still_failed}: {md_path}"
            )
        return md_path
