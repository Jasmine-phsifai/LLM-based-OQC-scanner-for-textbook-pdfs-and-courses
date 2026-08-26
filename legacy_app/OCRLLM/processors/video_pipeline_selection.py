"""
录课视频的两条独立管线选择模型。

视频里其实有两个互不依赖的产物：

- ``audio``  管线：提取音频 → 语音识别 → ``{stem}_录音识别.md``
- ``frames`` 管线：智能抽帧 → 完整帧等比例缩放 → 大模型识别 → ``{stem}_板书识别.md``

两者唯一的联系是热词：frames 管线识别出的热词可以喂给 audio 管线提升 ASR
质量。这是可选的加分项，不是执行顺序上的依赖 —— 缺热词时 audio 管线照常运行。

历史上这两条管线被压平成 1~5 五个有序阶段，导致「只补录音识别」「只重跑板书
识别」这类操作无法表达。这里保留 1~5 作为**稳定的步骤编号**（检查点文件、CLI
``--phases``、社交长视频处理器仍在用），但调度、产物清理和界面一律以管线为单位。
"""

from __future__ import annotations

from dataclasses import dataclass

AUDIO_STEPS = (1, 5)
FRAME_STEPS = (2, 3, 4)

STEP_AUDIO_EXTRACT = 1
STEP_FRAME_EXTRACT = 2
STEP_FRAME_RECOGNIZE = 4
STEP_AUDIO_RECOGNIZE = 5


@dataclass(frozen=True)
class VideoPipelineSelection:
    """用户要跑哪几条管线。"""

    frames: bool = True
    audio: bool = True
    audio_extract_only: bool = False
    """兼容旧的 ``phases=[1]``：只抽出 mp3，不做语音识别。"""

    @property
    def runs_audio_extract(self) -> bool:
        return self.audio or self.audio_extract_only

    @property
    def runs_audio_recognize(self) -> bool:
        return self.audio

    def steps(self) -> list[int]:
        """展开成稳定步骤编号，供检查点与旧接口使用。"""
        selected: list[int] = []
        if self.runs_audio_extract:
            selected.append(STEP_AUDIO_EXTRACT)
        if self.frames:
            selected.extend(FRAME_STEPS)
        if self.runs_audio_recognize:
            selected.append(STEP_AUDIO_RECOGNIZE)
        return sorted(selected)

    def owns_step(self, step: int) -> bool:
        if step in AUDIO_STEPS:
            return self.runs_audio_extract if step == STEP_AUDIO_EXTRACT else self.runs_audio_recognize
        return self.frames

    @classmethod
    def from_legacy_steps(cls, steps: list[int] | None, skip_audio: bool = False) -> VideoPipelineSelection:
        """把旧的 1~5 阶段勾选翻译成两条管线。

        Args:
            steps: 旧的阶段编号列表；``None`` 表示全选。
            skip_audio: 旧接口里与「不勾第 5 阶段」重复的开关。
        """
        if steps is None:
            steps = [1, 2, 3, 4] if skip_audio else [1, 2, 3, 4, 5]
        chosen = {int(step) for step in steps}
        wants_recognize = STEP_AUDIO_RECOGNIZE in chosen and not skip_audio
        wants_extract = STEP_AUDIO_EXTRACT in chosen
        return cls(
            frames=bool(chosen & set(FRAME_STEPS)),
            audio=wants_recognize,
            audio_extract_only=wants_extract and not wants_recognize,
        )

    def describe(self) -> str:
        parts = []
        if self.frames:
            parts.append("板书识别")
        if self.runs_audio_recognize:
            parts.append("录音识别")
        elif self.audio_extract_only:
            parts.append("仅提取音频")
        return " + ".join(parts) or "未选择任何管线"
