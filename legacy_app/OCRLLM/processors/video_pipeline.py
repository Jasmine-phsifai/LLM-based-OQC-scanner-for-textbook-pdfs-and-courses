"""
录课视频阶段管线框架 — 两条独立管线（audio / frames）的步骤生命周期。

步骤编号 1~5 保持不变（检查点文件、CLI ``--phases``、社交长视频处理器仍在用），
但归属关系由 :mod:`OCRLLM.processors.video_pipeline_selection` 定义：
步骤 1/5 属于 audio 管线，步骤 2/3/4 属于 frames 管线。任何失效重算都只在**同一条
管线内部**扩散，一条管线永远不会删掉另一条管线的产物。
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from OCRLLM.processors.video_pipeline_selection import (
    AUDIO_STEPS,
    FRAME_STEPS,
    VideoPipelineSelection,
)

if TYPE_CHECKING:
    from OCRLLM.core.checkpoint import Checkpoint
    from OCRLLM.processors.video import VideoProcessor

logger = logging.getLogger(__name__)


def _pipeline_steps_for(step: int) -> tuple[int, ...]:
    """返回该步骤所属管线的全部步骤编号。"""
    return AUDIO_STEPS if step in AUDIO_STEPS else FRAME_STEPS


def _downstream_steps_in_same_pipeline(
    context: "VideoProcessContext", step: int, inclusive: bool = True
) -> set[int]:
    """某步骤需要重算时，同一条管线内还需要一并作废的步骤。

    跨管线永远返回空集：重跑板书识别不会删掉录音识别结果，反之亦然。

    Args:
        inclusive: 是否包含该步骤自身。恢复失败时包含，重新执行成功时不包含。
    """
    siblings = _pipeline_steps_for(step)
    downstream = {sibling for sibling in siblings if sibling > step or (inclusive and sibling == step)}
    return {sibling for sibling in downstream if context.selection.owns_step(sibling)}


@dataclass
class VideoProcessContext:
    """视频处理步骤间数据传递容器。"""
    video_path: str
    output_dir: str
    frames_dir: str
    debug_dir: str
    info_path: str
    stem: str
    selection: VideoPipelineSelection
    prompt_template: str | None = None
    audio_prompt_template: str | None = None
    resume: bool = False
    cleanup_intermediates: bool = True
    audio_path: str | None = None
    frame_results: list[dict] | None = None
    processed_paths: list[str] | None = None
    hotwords: list[str] = field(default_factory=list)
    board_md: str | None = None
    halt_result: dict | None = None

    @property
    def selected_phases(self) -> list[int]:
        """旧接口兼容：展开成 1~5 步骤编号。"""
        return self.selection.steps()

    @property
    def skip_audio(self) -> bool:
        """旧接口兼容：是否不做语音识别。"""
        return not self.selection.runs_audio_recognize

    def to_result(self) -> dict:
        """将处理上下文转换为结果字典。

        Returns:
            包含 board_md、hotwords、audio_path 等的字典。
        """
        return {
            "board_md": self.board_md or os.path.join(self.output_dir, f"{self.stem}_板书识别.md"),
            "hotwords": self.hotwords,
            "audio_path": self.audio_path,
            "transcript_md": os.path.join(self.output_dir, f"{self.stem}_录音识别.md"),
            "frames": self.frame_results or [],
            "output_dir": self.output_dir,
            "frames_dir": self.frames_dir,
        }


class VideoPhase:
    """视频处理阶段基类 — 定义阶段生命周期接口。"""
    phase_id: int = 0
    phase_key: str = ""
    phase_name: str = ""

    def should_run(self, context: VideoProcessContext) -> bool:
        """判断该步骤是否应执行（基于用户选择的管线）。"""
        return context.selection.owns_step(self.phase_id)

    def phase_total(self, processor: VideoProcessor, context: VideoProcessContext) -> int:
        """返回该阶段的总步数（供进度追踪）。"""
        return 0

    def can_resume(self, processor: VideoProcessor, context: VideoProcessContext) -> bool:
        """判断该阶段的产物是否可恢复（断点续传）。"""
        return True

    def on_resume(self, processor: VideoProcessor, context: VideoProcessContext):
        """阶段恢复时的回调（跳过执行，加载已有产物）。"""
        logger.info("[VIDEO] 跳过 %s (已完成)", self.phase_name)

    def execute(self, processor: VideoProcessor, context: VideoProcessContext) -> bool:
        """执行阶段逻辑（子类必须实现）。

        Returns:
            True 继续后续阶段，False 中止管线。
        """
        raise NotImplementedError

    def run(
        self,
        processor: VideoProcessor,
        context: VideoProcessContext,
        checkpoint: Checkpoint,
        completed_phases: set[int],
    ) -> bool:
        """阶段运行入口 — 检查跳过/恢复/执行，并管理检查点。

        Returns:
            True 继续后续阶段，False 中止。
        """
        if not self.should_run(context):
            return True

        if self.phase_id in completed_phases:
            if self.can_resume(processor, context):
                self.on_resume(processor, context)
                return True

            invalidated = _downstream_steps_in_same_pipeline(context, self.phase_id)
            completed_phases.difference_update(invalidated)
            processor._clear_invalidated_phase_artifacts(context.output_dir, context.stem, invalidated)
            checkpoint.replace_completed(completed_phases)
            processor.checkpoint_mgr.save(checkpoint)
            logger.warning(
                "[VIDEO] %s 的恢复产物缺失或不一致，重新执行步骤 %s",
                self.phase_name,
                sorted(invalidated or {self.phase_id}),
            )

        if context.resume and self.phase_id not in completed_phases and self.can_resume(processor, context):
            logger.info("[VIDEO] 发现可复用产物，跳过 %s", self.phase_name)
            self.on_resume(processor, context)
            completed_phases.add(self.phase_id)
            processor.checkpoint_mgr.save_incremental(checkpoint, self.phase_id)
            return True

        processor.tracker.start_phase(
            self.phase_key,
            self.phase_name,
            self.phase_total(processor, context),
        )
        should_continue = self.execute(processor, context)
        processor.tracker.finish_phase(self.phase_key)
        if should_continue:
            processor.checkpoint_mgr.save_incremental(checkpoint, self.phase_id)
        return should_continue


class AudioExtractPhase(VideoPhase):
    """阶段 1 — 从视频提取音频。"""

    def phase_total(self, processor: VideoProcessor, context: VideoProcessContext) -> int:
        return 1

    phase_id = 1
    phase_key = "phase1"
    phase_name = "录音·提取音频"

    def can_resume(self, processor: VideoProcessor, context: VideoProcessContext) -> bool:
        """检查音频文件是否已存在。"""
        audio_path = processor._phase1_audio_path(context.output_dir, context.stem)
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
            context.audio_path = audio_path
            return True
        return False

    def on_resume(self, processor: VideoProcessor, context: VideoProcessContext):
        """恢复时加载已有音频路径。"""
        context.audio_path = processor._phase1_audio_path(context.output_dir, context.stem)
        super().on_resume(processor, context)

    def execute(self, processor: VideoProcessor, context: VideoProcessContext) -> bool:
        """执行音频提取。"""
        context.audio_path = processor._phase1_audio(context.video_path, context.output_dir, context.stem)
        return True


class FrameExtractPhase(VideoPhase):
    """阶段 2 — 智能抽帧。"""

    def phase_total(self, processor: VideoProcessor, context: VideoProcessContext) -> int:
        return 1

    phase_id = 2
    phase_key = "phase2"
    phase_name = "板书·智能抽帧"

    def can_resume(self, processor: VideoProcessor, context: VideoProcessContext) -> bool:
        """检查帧信息 JSON 文件是否有效。"""
        frame_results = processor._load_frame_info_if_valid(context.info_path)
        if frame_results is None:
            return False
        context.frame_results = frame_results
        return True

    def on_resume(self, processor: VideoProcessor, context: VideoProcessContext):
        """恢复时加载已有帧信息。"""
        context.frame_results = processor._load_frame_info(context.info_path)
        super().on_resume(processor, context)

    def execute(self, processor: VideoProcessor, context: VideoProcessContext) -> bool:
        """执行智能抽帧。"""
        context.frame_results = processor._phase2_extract(context.video_path, context.frames_dir, context.debug_dir)
        if not context.frame_results:
            logger.warning("[VIDEO] 未抽到任何帧")
            context.halt_result = {
                "board_md": None,
                "hotwords": [],
                "audio_path": context.audio_path,
                "frames": [],
                "output_dir": context.output_dir,
                "frames_dir": context.frames_dir,
            }
            return False

        with open(context.info_path, "w", encoding="utf-8") as f:
            json.dump(context.frame_results, f, ensure_ascii=False, indent=2)

        processor._clear_invalidated_phase_artifacts(
            context.output_dir,
            context.stem,
            _downstream_steps_in_same_pipeline(context, self.phase_id, inclusive=False),
        )
        context.processed_paths = None
        context.board_md = None
        context.hotwords = []
        return True


class FramePreprocessPhase(VideoPhase):
    """阶段 3 — 帧裁剪缩放预处理。"""
    phase_id = 3
    phase_key = "phase3"
    phase_name = "板书·裁剪缩放"

    def phase_total(self, processor: VideoProcessor, context: VideoProcessContext) -> int:
        """返回帧数量。"""
        if context.frame_results is None:
            context.frame_results = processor._load_frame_info(context.info_path)
        return len(context.frame_results)

    def can_resume(self, processor: VideoProcessor, context: VideoProcessContext) -> bool:
        """检查预处理后的图片是否全部存在。"""
        if context.frame_results is None:
            context.frame_results = processor._load_frame_info_if_valid(context.info_path)
        if context.frame_results is None:
            return False
        processed_paths = processor._load_phase3_processed_paths(context.output_dir, context.frame_results)
        if processed_paths is None:
            return False
        context.processed_paths = processed_paths
        return True

    def on_resume(self, processor: VideoProcessor, context: VideoProcessContext):
        """恢复时加载已有预处理路径。"""
        if context.frame_results is None:
            context.frame_results = processor._load_frame_info(context.info_path)
        context.processed_paths = processor._load_phase3_processed_paths(context.output_dir, context.frame_results)
        super().on_resume(processor, context)

    def execute(self, processor: VideoProcessor, context: VideoProcessContext) -> bool:
        """执行帧预处理。"""
        if context.frame_results is None:
            context.frame_results = processor._load_frame_info(context.info_path)
        processor._clear_invalidated_phase_artifacts(
            context.output_dir,
            context.stem,
            _downstream_steps_in_same_pipeline(context, self.phase_id, inclusive=False),
        )
        context.board_md = None
        context.hotwords = []
        context.processed_paths = processor._phase3_preprocess(context.frame_results, context.output_dir)
        return True


class BoardRecognizePhase(VideoPhase):
    """阶段 4 — LLM 板书/课件识别。"""
    phase_id = 4
    phase_key = "phase4"
    phase_name = "板书·大模型识别"

    def phase_total(self, processor: VideoProcessor, context: VideoProcessContext) -> int:
        """返回批次数，而不是帧数量。"""
        if context.frame_results is None:
            context.frame_results = processor._load_frame_info(context.info_path)
        frame_count = len(context.frame_results)
        batch_size = max(1, processor.cfg.video.batch_size)
        return (frame_count + batch_size - 1) // batch_size

    def can_resume(self, processor: VideoProcessor, context: VideoProcessContext) -> bool:
        """检查板书识别 Markdown 是否已存在。"""
        if context.frame_results is None:
            context.frame_results = processor._load_frame_info_if_valid(context.info_path)
        resume_state = processor._load_phase4_resume_state(
            context.output_dir,
            context.stem,
            frame_results=context.frame_results,
        )
        if resume_state is None:
            return False
        context.board_md = resume_state["board_md"]
        context.hotwords = resume_state["hotwords"]
        return True

    def on_resume(self, processor: VideoProcessor, context: VideoProcessContext):
        """恢复时加载板书 MD、热词和帧信息。"""
        super().on_resume(processor, context)
        if context.frame_results is None:
            context.frame_results = processor._load_frame_info_if_valid(context.info_path)
        resume_state = processor._load_phase4_resume_state(
            context.output_dir,
            context.stem,
            frame_results=context.frame_results,
        )
        if resume_state is not None:
            context.board_md = resume_state["board_md"]
            context.hotwords = resume_state["hotwords"]
        if context.frame_results is not None:
            context.processed_paths = processor._load_phase3_processed_paths(context.output_dir, context.frame_results)

    def execute(self, processor: VideoProcessor, context: VideoProcessContext) -> bool:
        """执行 LLM 板书/课件识别。"""
        if context.frame_results is None:
            context.frame_results = processor._load_frame_info(context.info_path)
        if context.processed_paths is None:
            context.processed_paths = processor._load_phase3_processed_paths(context.output_dir, context.frame_results)
        if context.processed_paths is None:
            logger.warning("[VIDEO] 预处理产物缺失，重新执行 Phase 3 以保持识别一致性")
            context.processed_paths = processor._phase3_preprocess(context.frame_results, context.output_dir)

        # 清理产物前先把上一次写了一半的板书 MD 拆成批次，避免重复付费识别。
        restored_slots: dict[int, str] = {}
        if context.resume:
            restored_slots = processor._load_phase4_partial_slots(
                context.output_dir,
                context.stem,
                context.frame_results,
                max(1, processor.cfg.video.batch_size),
            )

        board_md, hotwords, _ = processor._phase4_llm(
            context.frame_results,
            context.processed_paths,
            context.output_dir,
            context.stem,
            prompt_template=context.prompt_template,
            restored_slots=restored_slots,
        )
        context.board_md = board_md
        context.hotwords = hotwords
        return True


class AudioRecognizePhase(VideoPhase):
    """阶段 5 — 语音识别。"""

    def phase_total(self, processor: VideoProcessor, context: VideoProcessContext) -> int:
        return 1

    phase_id = 5
    phase_key = "phase5"
    phase_name = "录音·语音识别"

    def should_run(self, context: VideoProcessContext) -> bool:
        """仅在用户选了 audio 管线时执行。"""
        return context.selection.runs_audio_recognize

    def can_resume(self, processor: VideoProcessor, context: VideoProcessContext) -> bool:
        """检查转写结果文件是否已存在。"""
        transcript_path = processor._phase5_output_path(context.output_dir, context.stem)
        if os.path.exists(transcript_path) and os.path.getsize(transcript_path) > 0:
            if getattr(getattr(processor, "cfg", None), "google_api", None) and processor.cfg.google_api.enabled:
                from OCRLLM.processors.audio import google_audio_transcript_md_valid

                if not google_audio_transcript_md_valid(transcript_path, expected_terms=context.hotwords):
                    logger.warning("[VIDEO] Google audio transcript failed validation; rerunning Phase 5")
                    return False
            context.audio_path = processor._phase1_audio_path(context.output_dir, context.stem)
            return True
        return False

    def on_resume(self, processor: VideoProcessor, context: VideoProcessContext):
        """恢复时加载音频路径。"""
        context.audio_path = processor._phase1_audio_path(context.output_dir, context.stem)
        super().on_resume(processor, context)

    def execute(self, processor: VideoProcessor, context: VideoProcessContext) -> bool:
        """执行语音识别。音频丢失时先重新抽取（免费操作），而不是静默跳过。"""
        if context.audio_path is None:
            context.audio_path = processor._phase1_audio_path(context.output_dir, context.stem)
        if not os.path.exists(context.audio_path):
            logger.info("[VIDEO] 音频产物不在了，从视频重新提取后再识别")
            context.audio_path = processor._phase1_audio(
                context.video_path, context.output_dir, context.stem
            )
        if not os.path.exists(context.audio_path):
            raise RuntimeError(f"语音识别无法进行：音频提取失败 {context.audio_path}")
        processor._phase5_asr(
            context.audio_path,
            context.hotwords,
            context.output_dir,
            context.stem,
            prompt_template=context.audio_prompt_template,
            resume=context.resume,
        )
        return True


def build_video_phase_chain(context: VideoProcessContext) -> list[VideoPhase]:
    """构建视频处理阶段链。

    Args:
        context: 视频处理上下文。

    Returns:
        应执行的阶段列表。
    """
    phases: list[VideoPhase] = [
        AudioExtractPhase(),
        FrameExtractPhase(),
        FramePreprocessPhase(),
        BoardRecognizePhase(),
        AudioRecognizePhase(),
    ]
    return [phase for phase in phases if phase.should_run(context)]
