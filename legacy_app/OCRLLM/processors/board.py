"""
板书/截图识别处理器 — 上下文连续多模态请求。
"""

from __future__ import annotations

import os
import logging
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

        concat_md_files(md_parts, output_path)
        if batches and successful_batches == 0:
            raise RuntimeError(f"板书识别全部 {len(batches)} 个批次失败，输出文件只包含错误信息: {output_path}")
        reason = failed_placeholder_quality_reason(
            "\n\n".join(md_parts), expected_units=len(batches), unit_name="批",
        )
        if reason:
            raise RuntimeError(f"板书识别输出包含识别失败且有效正文过少: {reason}: {output_path}")
        logger.info("[BOARD] 板书识别完成 -> %s", output_path)
        return output_path
