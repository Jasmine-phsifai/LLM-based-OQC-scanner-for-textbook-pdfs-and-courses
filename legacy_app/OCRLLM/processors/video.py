"""
录课视频处理器 — 统一的 5 阶段管线。

Phase 1: 音频提取
Phase 2: 智能抽帧（粗扫 + 变化区间细扫 + pHash 去重）
Phase 3: 完整帧等比例缩放
Phase 4: 大模型板书/课件识别 + 热词提取
Phase 5: 热词辅助语音识别（可选）

增强功能:
  - 进度追踪: 每个 phase 独立进度条和状态描述
  - 增量写入: Phase 4 识别结果实时写入 MD
  - 断点续传: 中断后可从上次 phase 继续
  - API 池: 付费模式下多 key 并行加速（PDF 和视频 Phase 4 统一无状态并行策略）
"""

from __future__ import annotations

import hashlib
import json
import os
import logging
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from OCRLLM.config import AppConfig
from OCRLLM.core.llm_client import LLMClient
from OCRLLM.core.provider_selection import (
    uses_google_for_vision,
    visual_allows_high_parallel,
    visual_parallel_requests,
    visual_request_stagger_seconds,
    visual_video_frame_batch_size,
)
from OCRLLM.core.provider_errors import is_provider_setup_error
from OCRLLM.core.task_runner import ProgressReporter, CancelledError
from OCRLLM.core.write_text_atomically import write_text_atomically
from OCRLLM.core.utils import (
    batch_list, ensure_dir, long_path, resize_image_if_needed, resolve_workers, strip_md_fence,
)
from OCRLLM.core.video_capture import open_video_capture
from OCRLLM.core.progress_tracker import ProgressTracker
from OCRLLM.core.incremental_writer import IncrementalMDWriter
from OCRLLM.core.checkpoint import Checkpoint
from OCRLLM.core.board_merge import _parse_frames
from OCRLLM.core.output_quality import failed_placeholder_quality_reason, looks_like_refusal
from OCRLLM.processors.base import BaseProcessor
from OCRLLM.core.document_model import SourceType
from OCRLLM.processors.video_pipeline import VideoProcessContext, build_video_phase_chain
from OCRLLM.processors.video_pipeline_selection import VideoPipelineSelection
from OCRLLM.imaging.audio_extractor import extract_audio
from OCRLLM.imaging.imwrite_unicode import imwrite_unicode
from OCRLLM import prompts

logger = logging.getLogger(__name__)

_FRAME_META_RE = re.compile(
    r"^<!--\s*meta:frame\s+id=(\S+?)(?:\s+time=(\d{1,3}:\d{2}))?\s*-->$",
    flags=re.MULTILINE,
)

_FAILED_FRAME_RE = re.compile(
    r"<!--\s*帧\s+(\S+?)\s+识别失败:\s*.*?-->",
)
_FAILED_BATCH_RE = re.compile(
    r"<!--\s*批次\s+(\d+)\s+失败:\s*.*?-->",
)


class VideoProcessor(BaseProcessor):
    """
    录课视频 → Markdown 处理器。

    用法:
        proc = VideoProcessor()
        proc.process("lecture.mp4")

    带参数:
        proc = VideoProcessor(cfg=AppConfig().with_updates(video={"frame_interval": 5.0}))
        proc.process("lecture.mp4", phases=[1,2,3,4])
    """

    processor_key = "video"
    display_name = "录课视频识别"
    supported_extensions = (".mp4", ".avi", ".mkv", ".mov", ".flv", ".wmv")
    source_type = SourceType.VIDEO

    @staticmethod
    def _normalize_phases(phases: list[int] | None, skip_audio: bool) -> list[int]:
        if phases is None:
            phases = [1, 2, 3, 4] if skip_audio else [1, 2, 3, 4, 5]
        return list(dict.fromkeys(phases))

    @staticmethod
    def _debug_dir_name(stem: str) -> str:
        """Return a Windows-safe temp debug directory name for a source stem."""
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem)
        safe = re.sub(r"\s+", " ", safe).strip(" ._")
        if not safe:
            safe = "video"
        digest = hashlib.sha1(stem.encode("utf-8", errors="surrogatepass")).hexdigest()[:10]
        prefix = safe[:40].rstrip(" ._") or "video"
        return f"video_debug_{prefix}_{digest}"

    @staticmethod
    def _safe_output_stem(stem: str) -> str:
        """Return a filesystem-safe output artifact stem."""
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem)
        safe = re.sub(r"\s+", " ", safe).strip(" ._")
        return safe or "video"

    @staticmethod
    def _build_checkpoint_extra(
        stem: str,
        phases: list[int],
        skip_audio: bool,
        prompt_template: str | None,
        audio_prompt_template: str | None = None,
        output_stem: str | None = None,
        source_stem: str | None = None,
        cleanup_intermediates: bool = True,
    ) -> dict:
        extra = {
            "stem": stem,
            "phases": list(phases),
            "skip_audio": skip_audio,
            "prompt_template": prompt_template,
            "audio_prompt_template": audio_prompt_template,
        }
        if not cleanup_intermediates:
            extra["cleanup_intermediates"] = False
        if output_stem is not None:
            extra["output_stem"] = output_stem
        if source_stem is not None and source_stem != stem:
            extra["source_stem"] = source_stem
        return extra

    @staticmethod
    def _checkpoint_compat_extra(extra: dict) -> dict:
        """只比较真正影响产物含义的字段。

        管线选择（``phases``/``skip_audio``）故意排除在外：两条管线已经互不干扰，
        改勾选后仍应能复用磁盘上已有的产物，而不是从头重跑。
        """
        return {
            key: extra[key]
            for key in ("stem", "prompt_template", "audio_prompt_template", "output_stem", "source_stem")
            if key in extra
        }

    @classmethod
    def resume_options_from_checkpoint(cls, checkpoint: Checkpoint) -> dict:

        extra = checkpoint.extra or {}
        phases = extra.get("phases")
        normalized_phases = [int(phase) for phase in phases] if isinstance(phases, list) else None
        skip_audio = bool(extra.get("skip_audio", False))
        options = {
            "video_path": checkpoint.source_path,
            "output_dir": checkpoint.output_path,
            "phases": cls._normalize_phases(normalized_phases, skip_audio),
            "skip_audio": skip_audio,
            "prompt_template": extra.get("prompt_template") or None,
            "audio_prompt_template": extra.get("audio_prompt_template") or None,
            "resume": True,
        }
        if extra.get("cleanup_intermediates") is False:
            options["cleanup_intermediates"] = False
        if extra.get("output_stem"):
            options["output_stem"] = extra["output_stem"]
        return options

    @classmethod
    def default_output_dir(cls, cfg: AppConfig, video_path: str, output_stem: str = None) -> str:
        """返回该视频默认的输出目录（GUI 需要在启动前判断已有产物）。"""
        stem = cls._safe_output_stem(output_stem or Path(video_path).stem)
        return os.path.join(cfg.paths.output_dir, stem)

    @classmethod
    def existing_products(cls, cfg: AppConfig, video_path: str, output_dir: str = None) -> dict[str, bool]:
        """检查两条管线的识别结果是否已经在磁盘上。

        产物文件名的约定只在这里定义一次，GUI 不再自己拼路径。
        """
        stem = cls._safe_output_stem(Path(video_path).stem)
        directory = output_dir or cls.default_output_dir(cfg, video_path)
        return {
            "frames": cls._file_has_content(cls._phase4_board_path(directory, stem)),
            "audio": cls._file_has_content(cls._phase5_output_path(directory, stem)),
        }

    @staticmethod
    def find_failed_frames(md_path: str) -> list[str]:
        """Return frame IDs that have failure placeholders in the board MD."""
        try:
            text = Path(md_path).read_text(encoding="utf-8")
        except OSError:
            return []
        ids: list[str] = []
        for m in _FAILED_FRAME_RE.finditer(text):
            fid = m.group(1)
            if fid not in ids:
                ids.append(fid)
        return ids

    @staticmethod
    def find_failed_batch_indices(md_path: str) -> list[int]:
        """Return 1-based batch indices that have failure placeholders."""
        try:
            text = Path(md_path).read_text(encoding="utf-8")
        except OSError:
            return []
        indices: list[int] = []
        for m in _FAILED_BATCH_RE.finditer(text):
            idx = int(m.group(1))
            if idx not in indices:
                indices.append(idx)
        return sorted(indices)

    @staticmethod
    def board_has_failures(md_path: str) -> bool:
        """Check if board MD contains any failure markers."""
        try:
            text = Path(md_path).read_text(encoding="utf-8")
        except OSError:
            return False
        return bool(_FAILED_FRAME_RE.search(text) or _FAILED_BATCH_RE.search(text))

    def repair_board(
        self,
        video_path: str,
        output_dir: str,
        prompt_template: str = None,
    ) -> str:
        """Re-recognize failed frames in an existing board MD.

        Requires frame_info.json and frame images to still be on disk.
        Returns the md_path, or raises on total/partial failure.
        """
        stem = self._safe_output_stem(Path(video_path).stem)
        md_path = self._phase4_board_path(output_dir, stem)
        info_path = os.path.join(output_dir, "frame_info.json")
        prompt_template = prompt_template or prompts.BOARD_WITH_HOTWORDS

        failed_frame_ids = self.find_failed_frames(md_path)
        failed_batch_indices = self.find_failed_batch_indices(md_path)

        if not failed_frame_ids and not failed_batch_indices:
            logger.info("[VIDEO-REPAIR] 没有发现识别失败的帧: %s", md_path)
            return md_path
        if failed_batch_indices:
            failed = ", ".join(str(index) for index in failed_batch_indices)
            raise RuntimeError(
                "旧版视频输出只记录失败批次索引，历史帧成员无法证明，无法安全修复。"
                f"请重新执行视频板书识别以生成逐帧失败标记；失败批次: {failed}: {md_path}"
            )

        # Load frame info to resolve frame images
        frame_results = self._load_frame_info_if_valid(info_path)
        if frame_results is None:
            raise RuntimeError(
                f"帧信息文件 frame_info.json 不存在或无效，无法修复。"
                f"请勾选「保留中间文件」后重新处理视频，再尝试修复。"
            )

        # Build frame_id → (frame_dict, image_path) mapping
        manifest_path = self._phase3_manifest_path(output_dir)
        processed_map = {}
        if os.path.isfile(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                items = manifest.get("items") if isinstance(manifest, dict) else None
                if not isinstance(items, list):
                    logger.warning(
                        "[VIDEO-REPAIR] Phase 3 manifest 格式无效: %s",
                        manifest_path,
                    )
                    items = []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    src = item.get("source_path")
                    processed_path = item.get("processed_path")
                    if isinstance(src, str) and src:
                        processed_map[Path(src).stem] = (
                            processed_path
                            if isinstance(processed_path, str) and processed_path
                            else src
                        )
            except (json.JSONDecodeError, OSError, UnicodeError) as exc:
                logger.warning("[VIDEO-REPAIR] 读取 Phase 3 manifest 失败: %s", exc)

        # Resolve which frames to repair
        repair_targets: list[tuple[dict, str]] = []  # (frame_dict, image_path)
        unavailable_targets: list[str] = []

        # From per-frame failures
        frame_by_id = {Path(f.get("path", "")).stem: f for f in frame_results}
        for fid in failed_frame_ids:
            frame = frame_by_id.get(fid)
            if frame is None:
                unavailable_targets.append(fid)
                continue
            img = processed_map.get(fid) or frame.get("path", "")
            if os.path.isfile(img):
                repair_targets.append((frame, img))
            else:
                unavailable_targets.append(fid)

        if not repair_targets:
            raise RuntimeError(
                f"所有失败帧的图片文件均已丢失或无法定位，无法修复: {unavailable_targets}"
            )

        attempt_total = len(repair_targets)
        requested_total = attempt_total + len(unavailable_targets)
        logger.info("[VIDEO-REPAIR] 需要修复 %d 帧", requested_total)
        self._report(0, attempt_total, f"修复 {attempt_total} 个可用失败帧...")

        results: dict[str, str] = {}  # frame_id → recognized text
        still_failed: list[str] = list(unavailable_targets)
        content = Path(md_path).read_text(encoding="utf-8")

        for idx, (frame, img_path) in enumerate(repair_targets):
            self._check_cancelled()
            fid = Path(frame.get("path", "")).stem
            ts = frame.get("timestamp", 0)
            image_name = f"{fid} [{self._format_frame_time(ts)}]"
            self._report(
                idx + 1,
                attempt_total,
                f"识别帧 {fid} ({idx + 1}/{attempt_total})",
            )

            prompt = prompt_template.format(image_names=image_name, extra_instruction="")
            try:
                if self._use_api_pool_for_llm():
                    with self.api_pool.get_client() as client:
                        result = client.chat_with_images(prompt=prompt, image_paths=[img_path])
                else:
                    result = self.llm.chat_with_images(prompt=prompt, image_paths=[img_path])
                text = strip_md_fence(result)
                text = self._ensure_batch_frame_markers(text, (frame,))
                if looks_like_refusal(text):
                    logger.warning("[VIDEO-REPAIR] 帧 %s 模型拒识", fid)
                    still_failed.append(fid)
                    continue
            except CancelledError:
                raise
            except Exception as e:
                if is_provider_setup_error(e):
                    raise
                logger.error("[VIDEO-REPAIR] 帧 %s 识别失败: %s", fid, e)
                still_failed.append(fid)
                continue

            updated_content = content
            replacement_count = 0

            pattern = re.compile(
                r"(<!--\s*meta:frame\s+id=" + re.escape(fid) + r"[^>]*-->\s*\n*)"
                r"(\s*<!--\s*帧\s+" + re.escape(fid) + r"\s+识别失败:.*?-->)",
                re.DOTALL,
            )
            updated_content, replacement_count = pattern.subn(
                text,
                updated_content,
                count=1,
            )
            if replacement_count == 0:
                standalone = re.compile(
                    r"<!--\s*帧\s+" + re.escape(fid) + r"\s+识别失败:.*?-->",
                )
                updated_content, replacement_count = standalone.subn(
                    text,
                    updated_content,
                    count=1,
                )

            if replacement_count != 1:
                raise RuntimeError(f"视频修复标记已变化，无法安全发布帧 {fid}: {md_path}")
            write_text_atomically(md_path, updated_content)
            content = updated_content
            results[fid] = text
            self._report_content(text, f"修复识别 — 帧 {fid}")

        if not results:
            raise RuntimeError(f"视频板书修复全部 {requested_total} 帧失败")

        logger.info(
            "[VIDEO-REPAIR] 修复完成: %d/%d 帧成功, %d 帧仍失败 -> %s",
            len(results), requested_total, len(still_failed), md_path,
        )
        if still_failed:
            raise RuntimeError(
                f"视频板书修复后仍有 {len(still_failed)} 帧失败: {still_failed}: {md_path}"
            )
        return md_path

    def process(
        self,
        video_path: str,
        output_dir: str = None,
        phases: list[int] = None,
        skip_audio: bool = False,
        prompt_template: str = None,
        audio_prompt_template: str = None,
        output_stem: str = None,
        resume: bool = False,
        selection: VideoPipelineSelection = None,
        cleanup_intermediates: bool = True,
    ) -> dict:
        """执行录课视频处理。

        视频含两条互不依赖的管线：frames（抽帧 → 完整帧缩放 → 板书识别）和
        audio（提取音频 → 语音识别）。两者可以单独重跑，重跑一条永远不会删掉
        另一条的产物。

        Args:
            video_path: 视频文件路径。
            output_dir: 输出目录。
            phases: 旧接口的 1~5 阶段编号；传了 ``selection`` 时忽略。
            skip_audio: 旧接口的跳过语音识别开关。
            prompt_template: 自定义板书识别提示词。
            audio_prompt_template: 自定义语音识别提示词。
            resume: 是否复用磁盘上已有的产物（断点续传 / 手动部分重跑）。
            selection: 两条管线的选择，优先于 ``phases``。
            cleanup_intermediates: 成功后是否删除可免费重建的中间文件。

        Returns:
            包含 board_md、hotwords、audio_path、frames 等的结果字典。
        """
        video_path = os.path.abspath(video_path)
        if not os.path.isfile(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        source_stem = Path(video_path).stem
        stem = self._safe_output_stem(output_stem) if output_stem else self._safe_output_stem(source_stem)
        if output_dir is None:
            output_dir = os.path.join(ensure_dir(self.cfg.paths.output_dir), stem)
        ensure_dir(output_dir)

        frames_dir = os.path.join(output_dir, "提取帧")
        ensure_dir(frames_dir)
        debug_dir = os.path.join(ensure_dir(self.cfg.paths.temp_dir), self._debug_dir_name(stem))
        ensure_dir(debug_dir)

        if selection is None:
            selection = VideoPipelineSelection.from_legacy_steps(phases, skip_audio)
        phases = selection.steps()
        skip_audio = not selection.runs_audio_recognize

        context = VideoProcessContext(
            video_path=video_path,
            output_dir=output_dir,
            frames_dir=frames_dir,
            debug_dir=debug_dir,
            info_path=os.path.join(output_dir, "frame_info.json"),
            stem=stem,
            selection=selection,
            prompt_template=prompt_template,
            audio_prompt_template=audio_prompt_template,
            resume=resume,
            cleanup_intermediates=cleanup_intermediates,
        )
        # 热词是跨管线的可选输入：只跑 audio 管线时从磁盘上上一次板书识别的产物里读。
        if selection.runs_audio_recognize and not selection.frames:
            context.hotwords = self._load_existing_hotwords(output_dir, stem)

        phase_chain = build_video_phase_chain(context)

        self.tracker.start_task(
            "video",
            total_items=len(phase_chain),
            phase_weights=self._build_phase_weights(phases),
        )
        logger.info("[VIDEO] 开始处理: %s, 阶段=%s", stem, phases)

        checkpoint = None
        completed_phases = set()
        checkpoint_extra = self._build_checkpoint_extra(
            stem,
            phases,
            skip_audio,
            prompt_template,
            audio_prompt_template,
            output_stem=output_stem,
            source_stem=source_stem,
            cleanup_intermediates=cleanup_intermediates,
        )
        if resume:
            checkpoint = self.checkpoint_mgr.load("video", video_path)
            if checkpoint and checkpoint.is_compatible(
                total_items=5,
                output_path=output_dir,
                expected_extra=self._checkpoint_compat_extra(checkpoint_extra),
            ):
                completed_phases = set(checkpoint.completed_indices)
                logger.info("[VIDEO] 断点续传: 已完成阶段 %s", sorted(completed_phases))
                self._report(0, len(phase_chain), f"断点续传: 跳过已完成的阶段 {sorted(completed_phases)}")
            else:
                if checkpoint is not None:
                    logger.warning("[VIDEO] 检查点与当前任务参数不兼容，忽略旧检查点")
                checkpoint = Checkpoint(
                    task_type="video",
                    source_path=video_path,
                    output_path=output_dir,
                    total_items=5,
                    extra=checkpoint_extra,
                )
        else:
            checkpoint = Checkpoint(
                task_type="video",
                source_path=video_path,
                output_path=output_dir,
                total_items=5,
                extra=checkpoint_extra,
            )

        checkpoint.replace_completed(completed_phases)
        self.checkpoint_mgr.save(checkpoint)

        for phase in phase_chain:
            if not phase.run(self, context, checkpoint, completed_phases):
                break

        if context.halt_result is not None:
            self.checkpoint_mgr.remove("video", video_path)
            return context.halt_result

        self.checkpoint_mgr.remove("video", video_path)
        self._prune_completed_outputs(context)

        bottleneck = self.tracker.get_bottleneck_report()
        if bottleneck:
            logger.info("[VIDEO] %s", bottleneck)

        return context.to_result()

    @staticmethod
    def _build_phase_weights(phases: list[int]) -> dict[str, float]:
        weights: dict[str, float] = {}
        if 1 in phases:
            weights["phase1"] = 1.0
        if 2 in phases:
            weights["phase2"] = 3.0
        if 3 in phases:
            weights["phase3"] = 2.0
        if 4 in phases:
            weights["phase4"] = 4.0
        if 5 in phases:
            weights["phase5"] = 2.0
        return weights

    def _load_existing_hotwords(self, output_dir: str, stem: str) -> list[str]:
        """从上一次 frames 管线的产物里读热词；读不到就算了。"""
        hotword_path = self._phase4_hotword_path(output_dir, stem)
        try:
            if os.path.isfile(hotword_path):
                with open(hotword_path, "r", encoding="utf-8") as f:
                    words = [line.strip() for line in f if line.strip()]
                if words:
                    logger.info("[VIDEO] 复用已有热词表 %d 个词: %s", len(words), hotword_path)
                    return words
        except OSError as e:
            logger.warning("[VIDEO] 读取热词表失败，按无热词处理: %s", e)

        board_md = self._phase4_board_path(output_dir, stem)
        try:
            words = _extract_hotwords_from_md(board_md)
        except OSError as e:
            logger.warning("[VIDEO] 读取板书 MD 失败，按无热词处理: %s", e)
            return []
        if words:
            logger.info("[VIDEO] 从已有板书 MD 提取热词 %d 个", len(words))
        return words

    def _phase4_batch_size(self) -> int:
        return visual_video_frame_batch_size(self.cfg)

    def _llm_parallel_requests(self) -> int:
        return visual_parallel_requests(self.cfg)

    def _llm_request_stagger_seconds(self) -> float:
        return visual_request_stagger_seconds(self.cfg)

    def _use_api_pool_for_llm(self) -> bool:
        return (not uses_google_for_vision(self.cfg)) and self.cfg.api.paid_mode and self.api_pool.pool_size > 1

    @staticmethod
    def _phase1_audio_path(output_dir: str, stem: str) -> str:
        return os.path.join(output_dir, f"{stem}.mp3")

    @staticmethod
    def _phase3_dir(output_dir: str) -> str:
        return os.path.join(output_dir, "processed_frames")

    @staticmethod
    def _phase3_manifest_path(output_dir: str) -> str:
        return os.path.join(output_dir, "processed_frame_manifest.json")

    @staticmethod
    def _phase4_board_path(output_dir: str, stem: str) -> str:
        return long_path(os.path.join(output_dir, f"{stem}_板书识别.md"))

    @staticmethod
    def _phase4_merged_board_path(output_dir: str, stem: str) -> str:
        return long_path(os.path.join(output_dir, f"{stem}_板书识别_合并.md"))

    @staticmethod
    def _phase4_hotword_path(output_dir: str, stem: str) -> str:
        return long_path(os.path.join(output_dir, f"{stem}_热词表.txt"))

    @staticmethod
    def _phase5_output_path(output_dir: str, stem: str) -> str:
        return long_path(os.path.join(output_dir, f"{stem}_录音识别.md"))
    @staticmethod
    def _format_frame_time(timestamp: float) -> str:
        return f"{int(timestamp // 60):02d}:{int(timestamp % 60):02d}"

    @classmethod
    def _build_frame_marker(cls, frame: dict) -> str:
        frame_id = Path(frame["path"]).stem
        return f"<!-- meta:frame id={frame_id} time={cls._format_frame_time(frame['timestamp'])} -->"

    @staticmethod
    def _extract_hotword_fallback_text(md_parts: list[str]) -> str:
        cleaned_parts: list[str] = []
        for part in md_parts:
            if not part:
                continue
            body_lines = [
                line
                for line in part.splitlines()
                if not line.strip().startswith("<!--")
            ]
            body = "\n".join(body_lines).strip()
            if body:
                cleaned_parts.append(body)
        return "\n".join(cleaned_parts).strip()

    @classmethod
    def _has_expected_batch_frame_markers(cls, result_text: str, frames: tuple[dict, ...]) -> bool:
        marker_ids = [match.group(1) for match in _FRAME_META_RE.finditer(result_text)]
        expected_ids = [Path(frame["path"]).stem for frame in frames]
        return marker_ids == expected_ids

    # ---- Phase 1: 音频提取 ----
    def _phase1_audio(self, video_path: str, output_dir: str, stem: str) -> str:
        self._report(1, 5, "提取音频...")
        audio_path = self._phase1_audio_path(output_dir, stem)
        if os.path.exists(audio_path):
            logger.info("[VIDEO] 音频已存在: %s", audio_path)
            return audio_path
        return extract_audio(video_path, audio_path, cancel_event=self.reporter.cancel_event)

    @staticmethod
    def _open_video_capture(video_path: str):
        return open_video_capture(video_path)

    # ---- Phase 2: 智能抽帧 ----
    def _phase2_extract(
        self, video_path: str, frames_dir: str, debug_dir: str
    ) -> list[dict]:
        self._report(2, 5, "智能抽帧中...")
        return self._phase2_extract_inner(video_path, frames_dir, debug_dir)

    def _phase2_extract_inner(
        self, video_path: str, frames_dir: str, debug_dir: str
    ) -> list[dict]:
        # ---- Step 1: 读取视频元数据（短生命周期 cap） ----
        meta_cap = self._open_video_capture(video_path)
        if not meta_cap.isOpened():
            raise RuntimeError(f"无法打开视频: {video_path}")
        try:
            fps = meta_cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(meta_cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if fps <= 0:
                raise RuntimeError(f"视频 FPS 无效 ({fps})，文件可能已损坏: {video_path}")
            duration = total_frames / fps
            logger.info("[VIDEO] FPS=%.1f, 总帧=%d, 时长=%.1f分钟",
                         fps, total_frames, duration / 60)

            self.tracker.update_phase("phase2", 0, f"扫描视频帧 (共 {total_frames} 帧, {duration/60:.1f} 分钟)")

        finally:
            meta_cap.release()

        cand_temp_dir = os.path.join(debug_dir, "candidates")
        ensure_dir(cand_temp_dir)

        # ---- Step 2: 粗扫（seek 模式，不再使用 grab() 逐帧跳过） ----
        scan_workers = min(4, max(1, os.cpu_count() or 1))
        if duration < 300 or total_frames < 5000:
            scan_workers = 1

        candidates = self._coarse_scan(
            video_path, fps, total_frames, cand_temp_dir, scan_workers,
        )

        # ---- Step 3: 细扫 ----
        self._refine_scan(video_path, fps, candidates, cand_temp_dir)

        # ---- Step 4: 校准 + 保存（不需要 cap） ----
        candidates.sort(key=lambda m: m["timestamp"])
        logger.info("[VIDEO] 合并后候选: %d 帧", len(candidates))

        selected = self._auto_calibrate_segmentation(candidates, duration)
        selected = sorted(selected, key=lambda item: (item["timestamp"], item["frame_idx"]))

        results = self._save_selected_frames(selected, candidates, frames_dir)

        self._report(2, 5, f"抽帧完成: {len(results)} 张关键帧")
        return results

    def _coarse_scan(
        self, video_path: str, fps: float, total_frames: int,
        cand_temp_dir: str, num_workers: int = 1,
    ) -> list[dict]:
        """Pass 1: seek 模式粗扫（直接跳到目标帧，避免 grab() 逐帧开销）。

        单线程或多线程统一入口；num_workers=1 时退化为串行。
        """
        import threading
        coarse_skip = max(1, int(fps * self.cfg.video.frame_interval))
        target_indices = list(range(0, total_frames, coarse_skip))
        total_targets = len(target_indices)

        self.tracker.update_phase(
            "phase2", 0,
            f"粗扫: {num_workers} 线程, {total_targets} 帧 (seek 模式)",
            total=total_targets,
        )

        progress_lock = threading.Lock()
        progress_counter = [0]
        all_candidates: list[list[dict]] = [[] for _ in range(num_workers)]
        all_skipped = [{"blank": 0} for _ in range(num_workers)]

        # 按线程交错分配目标帧（均匀分散 I/O 开销）
        segments = [target_indices[i::num_workers] for i in range(num_workers)]

        def _scan_segment(seg_idx: int, targets: list[int]):
            seg_cap = self._open_video_capture(video_path)
            try:
                if not seg_cap.isOpened():
                    logger.error("[VIDEO] 粗扫线程 %d 无法打开视频", seg_idx)
                    return
                seg_cands = all_candidates[seg_idx]
                seg_skip = all_skipped[seg_idx]

                for i, frame_idx in enumerate(targets):
                    if i % 20 == 0:
                        self._check_cancelled()
                    seg_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                    ret, frame = seg_cap.read()
                    if not ret:
                        continue
                    self._extract_candidate_from_frame(
                        frame, frame_idx, fps, seg_cands, seg_skip, cand_temp_dir,
                    )
                    if (i + 1) % 50 == 0:
                        with progress_lock:
                            progress_counter[0] += 50
                            pc = progress_counter[0]
                        self.tracker.update_phase(
                            "phase2", min(pc, total_targets),
                            f"粗扫: {min(pc, total_targets)}/{total_targets}",
                            total=total_targets,
                        )
            finally:
                seg_cap.release()

        executor = ThreadPoolExecutor(max_workers=num_workers, thread_name_prefix="video-coarse")
        future_map = {}
        try:
            for idx, seg_targets in enumerate(segments):
                future = executor.submit(_scan_segment, idx, seg_targets)
                future_map[future] = idx
            for future in self._iter_completed_futures(set(future_map)):
                future_map.pop(future, None)
                future.result()  # propagate exceptions
        finally:
            self._cancel_futures(future_map)
            executor.shutdown(wait=True, cancel_futures=True)

        # 合并所有段的候选
        candidates = []
        total_blank = 0
        for seg_cands, seg_skip in zip(all_candidates, all_skipped):
            candidates.extend(seg_cands)
            total_blank += seg_skip["blank"]

        candidates.sort(key=lambda m: m["timestamp"])
        logger.info(
            "[VIDEO] 粗扫 (%d 线程, seek): %d 候选, 空白=%d",
            num_workers,
            len(candidates),
            total_blank,
        )
        return candidates

    def _refine_scan(self, video_path, fps, candidates, cand_temp_dir):
        """Pass 2: 对变化显著的 gap 区间做细扫补充候选帧（seek 模式）。

        每个 worker 持有一个 cap，处理分配给它的所有 gap（避免反复 open/release）。
        """
        import threading
        gaps = []
        if len(candidates) >= 2:
            sorted_cands = sorted(candidates, key=lambda m: m["timestamp"])
            for i in range(1, len(sorted_cands)):
                d = _thumb_diff(sorted_cands[i - 1]["thumb"], sorted_cands[i]["thumb"])
                if d > self.cfg.video.change_threshold:
                    gaps.append((sorted_cands[i - 1]["timestamp"], sorted_cands[i]["timestamp"], d))

        if not gaps:
            return

        refine_skip = max(1, int(fps * self.cfg.video.refine_interval))
        existing = {m["frame_idx"] for m in candidates}
        existing_lock = threading.Lock()
        candidates_lock = threading.Lock()
        refine_before = len(candidates)
        num_workers = min(4, max(1, len(gaps)))

        # 按 worker 交错分配 gap，使每个 worker 分摊多个 gap
        gap_groups: list[list[tuple]] = [[] for _ in range(num_workers)]
        for gi, gap in enumerate(gaps):
            gap_groups[gi % num_workers].append(gap)

        def _refine_worker(worker_gaps: list[tuple]) -> list[dict]:
            """单个 worker：用一个 cap 处理分配的所有 gap。"""
            worker_cap = self._open_video_capture(video_path)
            all_cands: list[dict] = []
            try:
                if not worker_cap.isOpened():
                    return []
                for gap_start_t, gap_end_t, _ in worker_gaps:
                    self._check_cancelled()
                    start_idx = int(gap_start_t * fps) + refine_skip
                    end_idx = int(gap_end_t * fps)
                    if start_idx >= end_idx:
                        continue

                    gap_skipped = {"blank": 0}
                    frame_idx = start_idx
                    count = 0
                    while frame_idx < end_idx:
                        count += 1
                        if count % 20 == 0:
                            self._check_cancelled()

                        with existing_lock:
                            already = frame_idx in existing
                            if not already:
                                existing.add(frame_idx)

                        if not already:
                            worker_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                            ret, frame = worker_cap.read()
                            if ret:
                                self._extract_candidate_from_frame(
                                    frame, frame_idx, fps, all_cands, gap_skipped,
                                    cand_temp_dir,
                                )

                        frame_idx += refine_skip
            finally:
                worker_cap.release()
            return all_cands

        executor = ThreadPoolExecutor(max_workers=num_workers, thread_name_prefix="video-refine")
        future_map = {}
        try:
            for wg in gap_groups:
                if wg:
                    future = executor.submit(_refine_worker, wg)
                    future_map[future] = wg

            for future in self._iter_completed_futures(set(future_map)):
                future_map.pop(future, None)
                worker_cands = future.result()
                if worker_cands:
                    with candidates_lock:
                        candidates.extend(worker_cands)
        finally:
            self._cancel_futures(future_map)
            executor.shutdown(wait=True, cancel_futures=True)

        logger.info("[VIDEO] 细扫补充: %d 候选 (%d 个 gap, %d workers, seek 模式)",
                    max(0, len(candidates) - refine_before), len(gaps), num_workers)

    def _save_selected_frames(self, selected, candidates, frames_dir) -> list[dict]:
        """保存选中帧到输出目录并清理临时文件。"""
        for old in os.listdir(frames_dir):
            old_path = os.path.join(frames_dir, old)
            if os.path.isfile(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    pass

        selected_temps = {item.get("temp_path") for item in selected}
        results = []
        for i, item in enumerate(selected):
            filename = f"board_{i + 1:03d}_{item['timestamp']:.0f}s.jpg"
            dest = os.path.join(frames_dir, filename)
            tp = item.get("temp_path")
            if tp and os.path.exists(tp):
                shutil.move(tp, dest)
            elif "path" in item and os.path.exists(item["path"]):
                shutil.copy2(item["path"], dest)
            results.append({
                "path": dest,
                "timestamp": item["timestamp"],
                "frame_idx": item["frame_idx"],
            })

        for m in candidates:
            tp = m.get("temp_path")
            if tp and tp not in selected_temps and os.path.exists(tp):
                try:
                    os.remove(tp)
                except OSError:
                    pass
            m.pop("thumb", None)

        return results

    def _extract_candidate_from_frame(
        self, frame, frame_idx, fps, candidates, skipped, temp_dir
    ):
        timestamp = frame_idx / fps
        if _is_blank(frame, self.cfg.video.min_content_ratio):
            skipped["blank"] += 1
            return

        thumb = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (256, 256))
        temp_path = os.path.join(temp_dir, f"cand_{frame_idx:08d}.jpg")
        imwrite_unicode(temp_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        candidates.append({
            "temp_path": temp_path,
            "timestamp": timestamp,
            "frame_idx": frame_idx,
            "thumb": thumb,
        })

    def _segment_and_select(self, candidates: list[dict],
                             change_threshold=None, drift_threshold=None,
                             max_segment_sec=None, phash_threshold=None) -> list[dict]:
        """分段选帧，接受可选阈值参数（用于自动校准）。"""
        if len(candidates) <= 1:
            return list(candidates)

        ct = change_threshold if change_threshold is not None else self.cfg.video.change_threshold
        dt = drift_threshold if drift_threshold is not None else self.cfg.video.drift_threshold
        ms = max_segment_sec if max_segment_sec is not None else self.cfg.video.max_segment_sec
        pt = phash_threshold if phash_threshold is not None else self.cfg.video.phash_threshold

        # 双模式分段
        segments = []
        seg_start = 0
        for i in range(1, len(candidates)):
            adj = _thumb_diff(candidates[i - 1]["thumb"], candidates[i]["thumb"])
            drift = _thumb_diff(candidates[seg_start]["thumb"], candidates[i]["thumb"])
            if adj > ct or drift > dt:
                segments.append((seg_start, i - 1))
                seg_start = i
        segments.append((seg_start, len(candidates) - 1))

        # 超长段切割
        final_segs = []
        for ss, se in segments:
            seg = candidates[ss:se + 1]
            if not seg:
                continue
            dur = seg[-1]["timestamp"] - seg[0]["timestamp"]
            if dur <= ms:
                final_segs.append((ss, se))
            else:
                n = max(2, int(dur / ms + 0.5))
                part_dur = dur / n
                t_base = seg[0]["timestamp"]
                sub_s = ss
                for p in range(1, n):
                    cut = t_base + part_dur * p
                    best = sub_s
                    for j in range(sub_s, se + 1):
                        if candidates[j]["timestamp"] <= cut:
                            best = j
                        else:
                            break
                    if best > sub_s:
                        final_segs.append((sub_s, best))
                        sub_s = best + 1
                final_segs.append((sub_s, se))

        reps = [candidates[se] for _, se in final_segs]
        return _phash_dedup(reps, pt)

    def _auto_calibrate_segmentation(
        self, candidates: list[dict], duration: float
    ) -> list[dict]:
        """自动校准分段参数，使输出帧数落在与视频时长成比例的目标范围内。

        目标密度: 28~40 帧/小时 → 2.5h≈70-100帧, 1.5h≈42-60帧。
        通过二分搜索统一灵敏度乘子，调节 change_threshold / drift_threshold /
        max_segment_sec 三个旋钮，最多迭代 10 轮即可收敛到目标区间。
        """
        TARGET_LOW_PER_HOUR = 28.0
        TARGET_HIGH_PER_HOUR = 40.0
        MAX_ATTEMPTS = 10

        duration_hours = duration / 3600
        target_low = max(5, int(duration_hours * TARGET_LOW_PER_HOUR + 0.5))
        target_high = max(10, int(duration_hours * TARGET_HIGH_PER_HOUR + 0.5))
        target_mid = (target_low + target_high) / 2

        base_change = self.cfg.video.change_threshold
        base_drift = self.cfg.video.drift_threshold
        base_max_seg = self.cfg.video.max_segment_sec
        phash_thresh = self.cfg.video.phash_threshold

        # 二分搜索灵敏度乘子: 小 → 阈值低 → 分段多 → 帧多; 大 → 反之
        lo_sens, hi_sens = 0.2, 4.0
        best_selected = None
        best_dist = float("inf")

        for attempt in range(MAX_ATTEMPTS):
            sens = (lo_sens + hi_sens) / 2
            ct = base_change * sens
            dt = base_drift * sens
            ms = base_max_seg * sens

            selected = self._segment_and_select(
                candidates, ct, dt, ms, phash_thresh
            )
            count = len(selected)

            logger.info(
                "[VIDEO] 校准第%d轮: sens=%.3f → %d帧 (目标%d~%d)",
                attempt + 1, sens, count, target_low, target_high,
            )

            dist = abs(count - target_mid)
            if dist < best_dist:
                best_dist = dist
                best_selected = selected

            if target_low <= count <= target_high:
                logger.info(
                    "[VIDEO] 自动校准成功: %d帧, 灵敏度=%.3f "
                    "(change=%.4f, drift=%.4f, max_seg=%.0f)",
                    count, sens, ct, dt, ms,
                )
                return selected

            if count < target_low:
                hi_sens = sens  # 帧太少 → 需更多分段 → 减小灵敏度乘子
            else:
                lo_sens = sens  # 帧太多 → 需更少分段 → 增大灵敏度乘子

        logger.info(
            "[VIDEO] 校准%d轮后使用最佳结果: %d帧 (目标%d~%d)",
            MAX_ATTEMPTS, len(best_selected), target_low, target_high,
        )

        # 安全上限: 若仍超出目标，均匀子采样
        if len(best_selected) > target_high:
            step = len(best_selected) / target_high
            best_selected = [best_selected[int(i * step)] for i in range(target_high)]
            logger.info("[VIDEO] 安全上限均匀下采样: → %d帧", len(best_selected))

        return best_selected

    # ---- Phase 3: 完整帧等比例缩放（不裁剪，保留原始帧） ----
    def _phase3_resize_full_frames(self, frame_results: list[dict], output_dir: str) -> list[str]:
        self._report(3, 5, "完整帧缩放...")
        self._clear_phase3_artifacts(output_dir)
        temp_dir = ensure_dir(self._phase3_dir(output_dir))
        workers = resolve_workers(self.cfg.concurrency.video_resize_workers, len(frame_results), hard_cap=8)

        def _resize_one(idx: int, fr: dict) -> tuple[int, str]:
            try:
                dest = os.path.join(temp_dir, Path(fr["path"]).name)
                resized = resize_image_if_needed(
                    fr["path"], self.cfg.processing.image_max_side, self.cfg.processing.image_quality,
                    output_path=dest,
                )
                return idx, resized
            except Exception as e:
                logger.warning("[VIDEO] 缩放失败: %s", e)
                return idx, fr["path"]

        paths = [""] * len(frame_results)
        executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="video-resize")
        future_map = {}
        try:
            for idx, fr in enumerate(frame_results):
                self._check_cancelled()
                future = executor.submit(_resize_one, idx, fr)
                future_map[future] = idx

            done = 0
            for future in self._iter_completed_futures(set(future_map)):
                future_map.pop(future, None)
                idx, path = future.result()
                paths[idx] = path
                done += 1
                self.tracker.update_phase(
                    "phase3",
                    done,
                    f"完整帧缩放: {done}/{len(frame_results)}",
                    total=len(frame_results),
                )
        finally:
            self._cancel_futures(future_map)
            executor.shutdown(wait=False, cancel_futures=True)

        self._save_phase3_manifest(output_dir, frame_results, paths)
        return paths

    # ---- Phase 4: LLM 识别（无状态并行，与 PDF 保持统一策略） ----
    def _phase4_llm(
        self,
        frame_results: list[dict],
        processed_paths: list[str],
        output_dir: str,
        stem: str,
        prompt_template: str = None,
        restored_slots: dict[int, str] = None,
    ) -> tuple[str, list[str], str]:
        self._report(4, 5, "大模型识别板书...")
        prompt_template = prompt_template or prompts.BOARD_WITH_HOTWORDS

        data = list(zip(frame_results, processed_paths))
        batch_size = self._phase4_batch_size()
        batches = batch_list(data, batch_size)
        total_batches = len(batches)
        restored_slots = {
            index: text for index, text in (restored_slots or {}).items() if 0 <= index < total_batches
        }

        # 增量写入器
        md_path = self._phase4_board_path(output_dir, stem)
        writer = IncrementalMDWriter(
            md_path, total_slots=total_batches, truncate=not bool(restored_slots),
        )
        if restored_slots:
            writer.seed_slots(restored_slots)

        md_parts = [""] * total_batches
        hotwords: list[str] = []
        pending_indices = [index for index in range(total_batches) if index not in restored_slots]
        for index, text in restored_slots.items():
            md_parts[index] = text

        if restored_slots:
            self.tracker.update_phase("phase4", len(restored_slots), "已恢复断点内容")
        if not pending_indices:
            writer.finalize()
            logger.info("[VIDEO] Phase 4 全部批次均已存在，直接复用 -> %s", md_path)
            return self._phase4_finalize(md_path, md_parts, hotwords, output_dir, stem)

        pending_count = len(pending_indices)

        # 计算并行度（与 PDF 统一策略）
        high_parallel_provider = visual_allows_high_parallel(self.cfg)
        base_workers = resolve_workers(self._llm_parallel_requests(), pending_count, hard_cap=64 if high_parallel_provider else 8)
        if self._use_api_pool_for_llm() and pending_count > base_workers:
            workers = min(self.api_pool.max_parallel, pending_count, base_workers * self.api_pool.pool_size)
            logger.info("[VIDEO] 付费模式: 并行度提升 %d → %d (API 池 %d 个 key)",
                        base_workers, workers, self.api_pool.pool_size)
        else:
            workers = base_workers

        logger.info("[VIDEO] Phase 4: %d 张帧, %d 个批次 (每批 %d 张), 待处理 %d, workers=%d",
                    len(frame_results), total_batches, batch_size, pending_count, workers)

        stagger = self._llm_request_stagger_seconds() if pending_count > 4 else 0
        self.tracker.update_queue(max(0, pending_count - workers), min(workers, pending_count))

        executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="video-llm")
        future_map = {}
        successful_batches = 0
        failed_batches: list[int] = []
        try:
            for order, bi in enumerate(pending_indices):
                self._check_cancelled()
                future = executor.submit(
                    self._phase4_batch_one, bi, batches[bi], total_batches, prompt_template, writer,
                )
                future_map[future] = bi
                if stagger and order < pending_count - 1:
                    self._sleep(stagger)

            done = 0
            for future in self._iter_completed_futures(set(future_map)):
                bi = future_map.pop(future, None)
                if bi is None:
                    continue
                done += 1
                try:
                    idx, result_text, hw, success = future.result()
                    md_parts[idx] = result_text
                    if success:
                        successful_batches += 1
                    else:
                        failed_batches.append(idx + 1)
                    for word in hw or []:
                        if word not in hotwords:
                            hotwords.append(word)
                    self.tracker.update_phase("phase4", len(restored_slots) + done, f"完成第 {idx+1}/{total_batches} 批")
                    self._report(4, 5, f"识别板书: 完成 {done}/{pending_count}")
                    self._report_content(result_text, f"板书识别 — 批次 {idx + 1}/{total_batches}")

                    remaining = pending_count - done
                    running = min(workers, remaining)
                    self.tracker.update_queue(max(0, remaining - running), running)
                except CancelledError:
                    raise
                except Exception as e:
                    if is_provider_setup_error(e) or self.cfg.codex_vision.enabled:
                        logger.error("[VIDEO] 批次 %s 失败，中止 Phase 4: %s", bi, e)
                        raise
                    logger.error("[VIDEO] 批次 %s 异常: %s", bi, e)
                    self.tracker.increment_error()
        finally:
            self._cancel_futures(future_map)
            executor.shutdown(wait=True, cancel_futures=True)

        # 最终写入
        writer.finalize()
        self.tracker.update_phase("phase4", total_batches, "识别完成")
        if pending_count and successful_batches == 0 and not restored_slots:
            raise RuntimeError(f"视频板书识别全部 {pending_count} 个批次失败，输出文件只包含错误信息: {md_path}")
        if total_batches:
            reason = failed_placeholder_quality_reason(
                "\n\n".join(part for part in md_parts if part),
                expected_units=total_batches, unit_name="批",
            )
            if reason:
                raise RuntimeError(f"视频板书识别输出包含识别失败且有效正文过少: {reason}: {md_path}")
        if failed_batches:
            failed = ", ".join(str(batch) for batch in failed_batches)
            raise RuntimeError(f"视频板书识别输出包含识别失败，失败批次: {failed}: {md_path}")

        return self._phase4_finalize(md_path, md_parts, hotwords, output_dir, stem)

    def _phase4_finalize(
        self,
        md_path: str,
        md_parts: list[str],
        hotwords: list[str],
        output_dir: str,
        stem: str,
    ) -> tuple[str, list[str], str]:
        """写出热词表并返回板书识别产物。"""
        # ---- 热词: 若没拿到，从文本中回退提取 ----
        if not hotwords and self.cfg.codex_vision.enabled:
            logger.info("[VIDEO] Codex 模式跳过 Qwen 文本热词提取")
        elif not hotwords and self.cfg.video.extract_hotwords_with_text_model:
            logger.info("[VIDEO] 通过文本请求提取热词")
            self.tracker.start_phase("phase4_hotwords", "提取热词")
            try:
                all_text = self._extract_hotword_fallback_text(md_parts)
                if all_text.strip():
                    hw_prompt = (
                        "基于以下板书识别内容，" + prompts.EXTRACT_HOTWORDS
                        + "\n\n" + all_text[-3000:]
                    )
                    hw_result = self.llm.chat_text(prompt=hw_prompt)
                    hotwords = [
                        l.strip().lstrip("- •·*").strip()
                        for l in hw_result.split("\n")
                        if l.strip() and len(l.strip()) < 50
                    ]
                    logger.info("[VIDEO] 热词提取: %d 个", len(hotwords))
            except Exception as e:
                logger.warning("[VIDEO] 热词提取失败: %s", e)
            self.tracker.finish_phase("phase4_hotwords")
        elif not hotwords:
            logger.info("[VIDEO] 跳过文本模型热词提取")

        hw_path = self._phase4_hotword_path(output_dir, stem)
        with open(hw_path, "w", encoding="utf-8") as f:
            f.write("\n".join(hotwords))

        return md_path, hotwords, hw_path

    @staticmethod
    def _ensure_batch_frame_markers(result_text: str, frames: tuple) -> str:
        """确保单帧结果包含正确的 meta:frame 标记。

        多帧批次若标记数量不完整，应回退逐帧识别；这里只负责单帧归一化。
        """
        if len(frames) != 1 and "meta:frame" in result_text:
            return result_text

        marker = VideoProcessor._build_frame_marker(frames[0])
        cleaned = re.sub(
            r"^<!--\s*meta:frame\s+id=\S+?(?:\s+time=\d{1,3}:\d{2})?\s*-->\s*",
            "",
            result_text.strip(),
            flags=re.MULTILINE,
        ).strip()
        if not cleaned:
            return marker
        return f"{marker}\n\n{cleaned}"

    def _phase4_rerun_per_frame(
        self,
        frames: tuple[dict, ...],
        paths: tuple[str, ...],
        prompt_template: str,
    ) -> tuple[str, list[str], bool]:
        parts: list[str] = []
        success = False

        for frame, path in zip(frames, paths):
            self._check_cancelled()
            image_name = f"{Path(frame['path']).stem} [{self._format_frame_time(frame['timestamp'])}]"
            prompt = prompt_template.format(image_names=image_name, extra_instruction="")
            try:
                if self._use_api_pool_for_llm():
                    with self.api_pool.get_client() as client:
                        result = client.chat_with_images(prompt=prompt, image_paths=[path])
                else:
                    result = self.llm.chat_with_images(prompt=prompt, image_paths=[path])
                normalized = self._ensure_batch_frame_markers(strip_md_fence(result), (frame,))
                if looks_like_refusal(normalized):
                    raise RuntimeError("模型拒识：" + normalized.strip().splitlines()[-1][:80])
                success = True
            except CancelledError:
                raise
            except Exception as e:
                if is_provider_setup_error(e) or self.cfg.codex_vision.enabled:
                    raise
                logger.error("[VIDEO] 逐帧回退失败: %s", e)
                safe_err = str(e).replace("--", "\u2014")
                normalized = (
                    f"{self._build_frame_marker(frame)}\n\n"
                    f"<!-- 帧 {Path(frame['path']).stem} 识别失败: {safe_err} -->"
                )
            parts.append(normalized)

        return "\n\n".join(part.strip() for part in parts if part.strip()), [], success

    def _phase4_batch_one(
        self,
        bi: int,
        batch: list[tuple[dict, str]],
        total_batches: int,
        prompt_template: str,
        writer: IncrementalMDWriter,
    ) -> tuple[int, str, list[str], bool]:
        """处理单个 Phase 4 批次（无状态，供并行调用）。"""
        frames, paths = zip(*batch)
        names = []
        for f in frames:
            ts = f["timestamp"]
            names.append(f"{Path(f['path']).stem} [{int(ts // 60):02d}:{int(ts % 60):02d}]")
        names_str = ", ".join(names)

        prompt = prompt_template.format(
            image_names=names_str, extra_instruction=""
        )

        hotwords = []
        try:
            if self._use_api_pool_for_llm():
                with self.api_pool.get_client() as client:
                    result = client.chat_with_images(prompt=prompt, image_paths=list(paths))
            else:
                result = self.llm.chat_with_images(prompt=prompt, image_paths=list(paths))

            result_text = strip_md_fence(result)

            if not self._has_expected_batch_frame_markers(result_text, frames) or looks_like_refusal(result_text):
                if len(frames) > 1:
                    logger.warning(
                        "[VIDEO] 批次 %d 帧标记不完整或疑似模型拒识，回退逐帧识别 (%d 帧)",
                        bi + 1,
                        len(frames),
                    )
                    result_text, hotwords, success = self._phase4_rerun_per_frame(frames, paths, prompt_template)
                elif looks_like_refusal(result_text):
                    logger.error("[VIDEO] 批次 %d 模型拒识（非空但非识别内容）", bi + 1)
                    safe_err = "模型拒识：" + result_text.strip().splitlines()[0][:80]
                    result_text = f"{self._build_frame_marker(frames[0])}\n\n<!-- 帧 {Path(frames[0]['path']).stem} 识别失败: {safe_err} -->"
                    success = False
                else:
                    result_text = self._ensure_batch_frame_markers(result_text, frames)
                    success = True
            else:
                result_text = self._ensure_batch_frame_markers(result_text, frames)
                success = True

            writer.write_slot(bi, result_text)
            return bi, result_text, hotwords, success
        except CancelledError:
            raise
        except Exception as e:
            if is_provider_setup_error(e) or self.cfg.codex_vision.enabled:
                raise
            logger.error("[VIDEO] 批次 %d 失败: %s", bi + 1, e)
            safe_err = str(e).replace("--", "\u2014")
            placeholder = "\n\n".join(
                f"{self._build_frame_marker(frame)}\n\n"
                f"<!-- 帧 {Path(frame['path']).stem} 识别失败: {safe_err} -->"
                for frame in frames
            )
            writer.write_slot(bi, placeholder)
            return bi, placeholder, [], False

    # ---- Phase 5: 语音识别 ----
    def _phase5_asr(
        self,
        audio_path: str,
        hotwords: list[str],
        output_dir: str,
        stem: str,
        prompt_template: str | None = None,
        resume: bool = False,
    ):
        self._report(5, 5, "语音识别...")
        self.tracker.update_phase("phase5", 0, "准备语音识别...", total=1)
        from OCRLLM.processors.audio import AudioProcessor

        # 如果热词为空，尝试从板书 MD 末尾提取
        if not hotwords:
            self.tracker.update_phase("phase5", 0, "从板书内容提取热词...", total=1)
            hotwords = _extract_hotwords_from_md(
                self._phase4_board_path(output_dir, stem)
            )
            if hotwords:
                logger.info("[VIDEO] 从板书MD提取 %d 个热词", len(hotwords))
                hw_path = self._phase4_hotword_path(output_dir, stem)
                with open(hw_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(hotwords))

        self.tracker.update_phase("phase5", 0, "正在进行语音识别...", total=1)
        output_path = self._phase5_output_path(output_dir, stem)
        child_reporter = self._make_phase5_reporter()
        proc = AudioProcessor(
            cfg=self.cfg,
            reporter=child_reporter,
            tracker=self.tracker,
            api_pool=self.api_pool,
            llm=self.llm,
        )
        proc.process(
            audio_path=audio_path,
            hotwords=hotwords,
            output_path=output_path,
            prompt_template=prompt_template,
            resume=resume,
        )

    def _make_phase5_reporter(self) -> ProgressReporter:
        def _on_progress(current: int, total: int, msg: str):
            self.tracker.update_phase("phase5", current, msg, total=total)

        child = ProgressReporter(on_progress=_on_progress, on_content=self.reporter.on_content)
        child._cancelled = self.reporter.cancel_event
        return child

    @staticmethod
    def _load_frame_info(path: str) -> list[dict]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"帧信息文件不存在: {path}，需先运行抽帧阶段")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_frame_info_if_valid(self, path: str) -> list[dict] | None:
        try:
            frame_results = self._load_frame_info(path)
        except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
            logger.warning("[VIDEO] 帧信息无效，无法恢复: %s", e)
            return None

        if not frame_results:
            return None

        missing = [frame.get("path") for frame in frame_results if not os.path.exists(frame.get("path", ""))]
        if missing:
            logger.warning("[VIDEO] 抽帧产物缺失，无法恢复: %s", missing[0])
            return None
        return frame_results

    def _load_phase4_resume_state(
        self,
        output_dir: str,
        stem: str,
        frame_results: list[dict] | None = None,
    ) -> dict | None:
        board_md = self._phase4_board_path(output_dir, stem)
        if not os.path.exists(board_md) or os.path.getsize(board_md) == 0:
            return None

        try:
            raw_text = Path(board_md).read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("[VIDEO] 读取 Phase 4 板书 MD 失败: %s", e)
            return None

        board_text, inferred_hotwords = _split_hotwords(raw_text)
        if not board_text.strip():
            logger.warning("[VIDEO] Phase 4 板书 MD 为空，无法恢复")
            return None

        frames = _parse_frames(board_text)
        if not frames:
            logger.warning("[VIDEO] Phase 4 板书 MD 缺少可解析帧标题，无法恢复")
            return None

        if frame_results is not None:
            expected_ids = [Path(frame.get("path", "")).stem for frame in frame_results]
            actual_ids = [frame.get("frame_id") for frame in frames]
            if len(actual_ids) != len(expected_ids):
                logger.warning(
                    "[VIDEO] Phase 4 板书帧数与抽帧结果不一致，无法恢复: %d != %d",
                    len(actual_ids),
                    len(expected_ids),
                )
                return None
            if actual_ids != expected_ids:
                logger.warning("[VIDEO] Phase 4 板书帧标题与抽帧结果不匹配，无法恢复")
                return None

        hotword_path = self._phase4_hotword_path(output_dir, stem)
        hotwords = inferred_hotwords
        if os.path.exists(hotword_path):
            try:
                hotwords = [
                    line.strip()
                    for line in Path(hotword_path).read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            except OSError as e:
                logger.warning("[VIDEO] 读取 Phase 4 热词表失败: %s", e)
                return None

        return {
            "board_md": board_md,
            "hotwords": hotwords,
        }

    def _load_phase4_partial_slots(
        self,
        output_dir: str,
        stem: str,
        frame_results: list[dict],
        batch_size: int,
    ) -> dict[int, str]:
        """从上一次写了一半的板书 MD 里恢复已完成的批次，避免重复付费识别。

        以 markdown 自身为状态：一个批次的所有帧标记都在、顺序一致、内容既不是失败
        占位也不是模型拒识，才算这一批已完成。
        """
        board_md = self._phase4_board_path(output_dir, stem)
        if not self._file_has_content(board_md):
            return {}
        try:
            board_text, _ = _split_hotwords(Path(board_md).read_text(encoding="utf-8"))
        except OSError as e:
            logger.warning("[VIDEO] 读取板书 MD 失败，放弃批次级恢复: %s", e)
            return {}

        blocks = {
            frame["frame_id"]: "\n".join([frame["header"], *frame["lines"]]).strip()
            for frame in _parse_frames(board_text)
        }
        if not blocks:
            return {}

        restored: dict[int, str] = {}
        for batch_index, batch in enumerate(batch_list(list(frame_results), batch_size)):
            frame_ids = [Path(frame.get("path", "")).stem for frame in batch]
            if any(frame_id not in blocks for frame_id in frame_ids):
                continue
            text = "\n\n".join(blocks[frame_id] for frame_id in frame_ids)
            if "识别失败" in text or looks_like_refusal(text):
                continue
            restored[batch_index] = text
        if restored:
            logger.info("[VIDEO] 批次级恢复: 复用已完成的 %d 个批次", len(restored))
        return restored

    def _clear_phase3_artifacts(self, output_dir: str):
        manifest_path = self._phase3_manifest_path(output_dir)
        processed_dir = self._phase3_dir(output_dir)

        try:
            if os.path.exists(manifest_path):
                os.remove(manifest_path)
        except OSError as e:
            logger.warning("[VIDEO] 清理 Phase 3 manifest 失败: %s", e)

        try:
            if os.path.isdir(processed_dir):
                shutil.rmtree(processed_dir)
        except OSError as e:
            logger.warning("[VIDEO] 清理 Phase 3 产物目录失败: %s", e)

    def _clear_phase4_artifacts(self, output_dir: str, stem: str):
        for path, label in [
            (self._phase4_board_path(output_dir, stem), "Phase 4 板书 MD"),
            (self._phase4_merged_board_path(output_dir, stem), "Phase 4 合并板书 MD"),
            (self._phase4_hotword_path(output_dir, stem), "Phase 4 热词表"),
        ]:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError as e:
                logger.warning("[VIDEO] 清理 %s 失败: %s", label, e)

    def _clear_phase5_artifacts(self, output_dir: str, stem: str):
        transcript_path = self._phase5_output_path(output_dir, stem)
        try:
            if os.path.exists(transcript_path):
                os.remove(transcript_path)
        except OSError as e:
            logger.warning("[VIDEO] 清理 Phase 5 转写结果失败: %s", e)

    def _clear_invalidated_phase_artifacts(self, output_dir: str, stem: str, invalidated: set[int]):
        if 3 in invalidated:
            self._clear_phase3_artifacts(output_dir)
        if 4 in invalidated:
            self._clear_phase4_artifacts(output_dir, stem)
        if 5 in invalidated:
            self._clear_phase5_artifacts(output_dir, stem)

    def _prune_completed_outputs(self, context: VideoProcessContext):
        """成功完成后清理中间产物。

        只删除「不花钱就能重建」的东西：mp3 可以再从视频里抽，帧和完整帧缩放图可以再生成。
        识别结果（板书 MD、录音 MD、热词表）一律保留 —— 它们是花过钱的产物，而且是
        另一条管线以后单独重跑时的输入。
        """
        if not context.cleanup_intermediates:
            logger.info("[VIDEO] 已关闭中间文件清理，保留全部产物")
            return

        output_dir = context.output_dir
        stem = context.stem
        board_path = self._phase4_board_path(output_dir, stem)

        # Preserve intermediates when board MD has failures — needed for future repair
        if context.selection.frames and self.board_has_failures(board_path):
            logger.info("[VIDEO] 板书识别含失败帧，保留中间文件以便修复")
            return

        if context.selection.frames and not self._file_has_content(board_path):
            logger.warning("[VIDEO] 板书 MD 不存在或为空，跳过清理以便排查")
            return
        if context.selection.runs_audio_recognize and not self._file_has_content(
            self._phase5_output_path(output_dir, stem)
        ):
            logger.warning("[VIDEO] 录音识别结果不存在或为空，跳过清理以便排查")
            return

        if self._file_has_content(board_path):
            context.board_md = board_path

        audio_path = self._phase1_audio_path(output_dir, stem)
        keep_audio_for_repair = False
        if context.selection.runs_audio_recognize:
            from OCRLLM.processors.audio import AudioProcessor

            transcript_path = self._phase5_output_path(output_dir, stem)
            keep_audio_for_repair = bool(
                AudioProcessor.find_failed_segments(transcript_path)
            )
            if keep_audio_for_repair:
                logger.info("[VIDEO] 录音识别含失败分段，保留提取音频以便修复")

        cleanup_targets = [
            (context.info_path, "帧信息"),
            (self._phase4_merged_board_path(output_dir, stem), "合并板书 MD"),
        ]
        if not keep_audio_for_repair:
            cleanup_targets.append((audio_path, "提取的音频"))

        for path, label in cleanup_targets:
            try:
                if os.path.isfile(path):
                    os.remove(path)
                    logger.info("[VIDEO] 已清理 %s: %s", label, path)
            except OSError as e:
                logger.warning("[VIDEO] 清理 %s 失败: %s", label, e)

        try:
            if os.path.isdir(context.frames_dir):
                shutil.rmtree(context.frames_dir)
                logger.info("[VIDEO] 已清理提取帧目录: %s", context.frames_dir)
        except OSError as e:
            logger.warning("[VIDEO] 清理提取帧目录失败: %s", e)

        self._clear_phase3_artifacts(output_dir)

    @staticmethod
    def _file_has_content(path: str) -> bool:
        try:
            return os.path.isfile(path) and os.path.getsize(path) > 0
        except OSError:
            return False

    def _save_phase3_manifest(
        self,
        output_dir: str,
        frame_results: list[dict],
        processed_paths: list[str],
    ):
        manifest_path = self._phase3_manifest_path(output_dir)
        items = []
        for frame, processed_path in zip(frame_results, processed_paths):
            items.append({
                "source_path": frame.get("path"),
                "processed_path": processed_path,
                "timestamp": frame.get("timestamp"),
                "frame_idx": frame.get("frame_idx"),
            })

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({"items": items}, f, ensure_ascii=False, indent=2)

    def _load_phase3_processed_paths(
        self,
        output_dir: str,
        frame_results: list[dict] | None = None,
    ) -> list[str] | None:
        manifest_path = self._phase3_manifest_path(output_dir)
        if not os.path.exists(manifest_path):
            return None

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("[VIDEO] 读取 Phase 3 manifest 失败: %s", e)
            return None

        items = data.get("items")
        if not isinstance(items, list) or not items:
            return None

        if frame_results is not None and len(items) != len(frame_results):
            logger.warning("[VIDEO] Phase 3 manifest 数量与抽帧结果不一致，放弃恢复")
            return None

        processed_paths: list[str] = []
        for idx, item in enumerate(items):
            processed_path = item.get("processed_path")
            if not processed_path or not os.path.exists(processed_path):
                logger.warning("[VIDEO] Phase 3 产物缺失，放弃恢复: %s", processed_path)
                return None
            if frame_results is not None:
                source_path = item.get("source_path")
                expected_source = frame_results[idx].get("path")
                if source_path != expected_source:
                    logger.warning("[VIDEO] Phase 3 manifest 与当前抽帧结果不匹配，放弃恢复")
                    return None
            processed_paths.append(processed_path)

        return processed_paths


# ---- 无状态帧处理辅助函数 ----

def _thumb_diff(a: np.ndarray, b: np.ndarray) -> float:
    d = cv2.absdiff(a, b)
    _, t = cv2.threshold(d, 25, 255, cv2.THRESH_BINARY)
    return np.count_nonzero(t) / (256 * 256)


def _is_blank(img: np.ndarray, threshold: float) -> bool:
    if img is None or img.size == 0:
        return True
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 30, 100)
    return np.count_nonzero(edges) / (edges.shape[0] * edges.shape[1]) < threshold


def _compute_phash(gray: np.ndarray, size: int = 8) -> np.ndarray:
    resized = cv2.resize(gray, (size * 4, size * 4), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(np.float32(resized))
    low = dct[:size, :size]
    return (low > np.median(low)).flatten()


def _phash_dedup(frames: list[dict], threshold: int) -> list[dict]:
    if len(frames) <= 1:
        return sorted(frames, key=lambda item: (item.get("timestamp", 0), item.get("frame_idx", 0)))
    hashes = [_compute_phash(f["thumb"]) if "thumb" in f else None for f in frames]
    # 对没有frame的帧（从JSON恢复），跳过去重
    if any(h is None for h in hashes):
        return sorted(frames, key=lambda item: (item.get("timestamp", 0), item.get("frame_idx", 0)))

    selected, sel_h = [frames[0]], [hashes[0]]
    for i in range(1, len(frames)):
        distances = [int(np.count_nonzero(hashes[i] != sh)) for sh in sel_h]
        min_distance = min(distances)
        min_index = distances.index(min_distance)
        if min_distance < threshold:
            selected[min_index] = frames[i]
            sel_h[min_index] = hashes[i]
        else:
            selected.append(frames[i])
            sel_h.append(hashes[i])
    return sorted(selected, key=lambda item: (item.get("timestamp", 0), item.get("frame_idx", 0)))


def _extract_hotwords_from_md(md_path: str) -> list[str]:
    """从板书 MD 末尾提取热词列表（LLM 通常在最末追加）。"""
    if not os.path.exists(md_path):
        return []
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    _, hw = _split_hotwords(content)
    return hw


def _split_hotwords(text: str) -> tuple[str, list[str]]:
    # 只在最后 50 行范围内搜索热词标记，避免正文中出现 "# 热词" 时误切割
    lines = text.rstrip().split("\n")
    tail_limit = 50
    tail_start_idx = max(0, len(lines) - tail_limit)
    tail_text = "\n".join(lines[tail_start_idx:])

    # 方式1: 匹配标题标记（仅在末尾范围内搜索）
    for marker in ["# 热词", "## 热词", "### 热词", "热词表", "热词列表"]:
        pos = tail_text.rfind(marker)
        if pos != -1:
            # 换算回原文偏移
            head_len = len("\n".join(lines[:tail_start_idx]))
            if tail_start_idx > 0:
                head_len += 1  # 补上拼接处的换行符
            abs_pos = head_len + pos
            board = text[:abs_pos].strip()
            hw_section = text[abs_pos:].strip().split("\n")
            hw = [l.strip().lstrip("- •·*").strip() for l in hw_section[1:]]
            return board, [w for w in hw if w and len(w) < 50]

    # 方式2: 检测末尾连续短行（无标题的热词列表）
    # LLM 经常在最后一个 --- 分隔符后直接输出热词列表
    tail_hw = []
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if not line:
            continue
        # 热词行特征: 长度 < 30, 不含 # $ | [ 等 Markdown/公式符号
        if len(line) < 30 and not any(c in line for c in '#$|[](){}>*_='):
            tail_hw.append(line.lstrip("- •·").strip())
        else:
            break
    if len(tail_hw) >= 5:  # 至少5个热词才认为是热词列表
        tail_hw.reverse()
        cut = len(lines) - len(tail_hw)
        # 跳过热词前的空行
        while cut > 0 and not lines[cut - 1].strip():
            cut -= 1
        board = "\n".join(lines[:cut]).strip()
        return board, [w for w in tail_hw if w and len(w) < 50]

    return text, []
