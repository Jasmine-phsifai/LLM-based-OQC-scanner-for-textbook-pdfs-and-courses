"""
进度追踪器 — 线程安全的细粒度进度状态管理。

用于 PDF 和视频长时间任务，提供：
  - 实时百分比进度
  - 阶段文字描述（当前在做什么）
  - 队列信息（多少张在排队）
  - 瓶颈诊断（哪一步最慢）
"""

from __future__ import annotations

import threading
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PhaseInfo:
    """单个阶段的进度信息。"""
    name: str
    current: int = 0
    total: int = 0
    started_at: float = 0.0
    finished_at: float = 0.0
    description: str = ""

    @property
    def elapsed(self) -> float:
        """已用时间（秒），未完成则以当前时间计。"""
        if self.started_at <= 0:
            return 0.0
        end = self.finished_at if self.finished_at > 0 else time.time()
        return end - self.started_at

    @property
    def is_done(self) -> bool:
        """阶段是否已完成。"""
        return self.finished_at > 0

    @property
    def percent(self) -> float:
        """当前进度百分比 (0~100)。"""
        if self.total <= 0:
            return 0.0
        return min(100.0, self.current / self.total * 100.0)


class ProgressTracker:
    """线程安全的任务级进度追踪器。

    处理器写入进度 → GUI 定时轮询读取 → 显示人类友好的状态。
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._task_type: str = ""  # "pdf" / "video"
        self._phases: dict[str, PhaseInfo] = {}
        self._phase_weights: dict[str, float] = {}
        self._current_phase: str = ""
        self._status_message: str = ""
        self._queue_pending: int = 0
        self._queue_running: int = 0
        self._error_count: int = 0
        self._total_items: int = 0
        self._completed_items: int = 0
        self._started_at: float = 0.0
        self._phase_timings: dict[str, float] = {}

    def start_task(self, task_type: str, total_items: int = 0, phase_weights: Optional[dict[str, float]] = None):
        """初始化新任务追踪。

        Args:
            task_type: 任务类型标识（如 ``pdf``、``video``）。
            total_items: 总条目数。
        """
        with self._lock:
            self._task_type = task_type
            self._total_items = total_items
            self._completed_items = 0
            self._error_count = 0
            self._started_at = time.time()
            self._phases.clear()
            self._phase_weights = self._normalize_phase_weights(phase_weights)
            self._current_phase = ""
            self._status_message = ""
            self._queue_pending = 0
            self._queue_running = 0
            self._phase_timings.clear()

    def start_phase(self, phase_id: str, name: str, total: int = 0):
        """开始一个新的处理阶段。

        Args:
            phase_id: 阶段标识符。
            name: 阶段名称。
            total: 阶段总步数。
        """
        with self._lock:
            self._current_phase = phase_id
            self._phases[phase_id] = PhaseInfo(
                name=name, total=total, started_at=time.time()
            )
            self._status_message = f"正在{name}..."
            logger.info("[进度] 开始阶段: %s (%s), 共 %d 项", phase_id, name, total)

    def update_phase(self, phase_id: str, current: int, description: str = "", total: Optional[int] = None):
        """更新阶段进度。

        Args:
            phase_id: 阶段标识符。
            current: 当前步数。
            description: 进度描述文本。
        """
        with self._lock:
            if phase_id in self._phases:
                p = self._phases[phase_id]
                p.current = current
                if total is not None and total >= 0:
                    p.total = total
                if description:
                    p.description = description
                    self._status_message = description

    def finish_phase(self, phase_id: str):
        """标记阶段完成。

        Args:
            phase_id: 阶段标识符。
        """
        with self._lock:
            if phase_id in self._phases:
                p = self._phases[phase_id]
                p.finished_at = time.time()
                p.current = p.total
                self._phase_timings[phase_id] = p.elapsed
                logger.info("[进度] 完成阶段: %s, 耗时 %.1fs", phase_id, p.elapsed)

    def update_queue(self, pending: int, running: int):
        """更新队列状态信息。

        Args:
            pending: 排队等待数。
            running: 正在执行数。
        """
        with self._lock:
            self._queue_pending = pending
            self._queue_running = running

    def increment_completed(self, count: int = 1):
        """递增已完成条目计数。

        Args:
            count: 递增量，默认 1。
        """
        with self._lock:
            self._completed_items += count

    def increment_error(self):
        """递增错误计数。"""
        with self._lock:
            self._error_count += 1

    def set_total(self, total: int):
        """更新总条目数。

        Args:
            total: 新的总数。
        """
        with self._lock:
            self._total_items = total

    def set_status(self, msg: str):
        """设置状态消息文本。

        Args:
            msg: 状态消息。
        """
        with self._lock:
            self._status_message = msg

    # ---- 只读查询（GUI 轮询用） ----

    def get_snapshot(self) -> dict:
        """获取当前进度快照（线程安全副本）。"""
        with self._lock:
            phases = {}
            for pid, p in self._phases.items():
                phases[pid] = {
                    "name": p.name,
                    "current": p.current,
                    "total": p.total,
                    "percent": p.percent,
                    "elapsed": p.elapsed,
                    "is_done": p.is_done,
                    "description": p.description,
                }
            elapsed = time.time() - self._started_at if self._started_at > 0 else 0
            return {
                "task_type": self._task_type,
                "current_phase": self._current_phase,
                "status_message": self._status_message,
                "phases": phases,
                "queue_pending": self._queue_pending,
                "queue_running": self._queue_running,
                "total_items": self._total_items,
                "completed_items": self._completed_items,
                "error_count": self._error_count,
                "overall_percent": self._compute_overall_percent_locked(),
                "elapsed": elapsed,
                "phase_timings": dict(self._phase_timings),
            }

    @staticmethod
    def _normalize_phase_weights(phase_weights: Optional[dict[str, float]]) -> dict[str, float]:
        if not phase_weights:
            return {}
        cleaned = {
            str(phase_id): float(weight)
            for phase_id, weight in phase_weights.items()
            if weight and float(weight) > 0
        }
        total_weight = sum(cleaned.values())
        if total_weight <= 0:
            return {}
        return {phase_id: weight / total_weight for phase_id, weight in cleaned.items()}

    def _compute_overall_percent_locked(self) -> float:
        if self._phase_weights:
            total = 0.0
            for phase_id, weight in self._phase_weights.items():
                phase = self._phases.get(phase_id)
                if phase is None:
                    continue
                if phase.is_done:
                    fraction = 1.0
                elif phase.total > 0:
                    fraction = min(1.0, max(0.0, phase.current / phase.total))
                else:
                    fraction = 0.0
                total += weight * fraction
            return min(100.0, max(0.0, total * 100.0))

        if self._total_items > 0:
            return self._completed_items / self._total_items * 100.0
        return 0.0

    def get_friendly_message(self) -> str:
        """获取人类友好的进度描述（不包含错误信息）。"""
        snap = self.get_snapshot()
        parts = []

        if snap["task_type"] == "pdf":
            parts.append(self._pdf_friendly(snap))
        elif snap["task_type"] == "video":
            parts.append(self._video_friendly(snap))
        else:
            if snap["status_message"]:
                parts.append(snap["status_message"])

        return " | ".join(p for p in parts if p)

    def get_bottleneck_report(self) -> str:
        """日志用：报告最慢的阶段。"""
        with self._lock:
            if not self._phase_timings:
                return ""
            slowest = max(self._phase_timings, key=self._phase_timings.get)
            name = self._phases[slowest].name if slowest in self._phases else slowest
            return f"最慢阶段: {name} ({self._phase_timings[slowest]:.1f}s)"

    def _pdf_friendly(self, snap: dict) -> str:
        done = snap["completed_items"]
        total = snap["total_items"]
        pct = snap["overall_percent"]
        if total <= 0:
            return snap.get("status_message", "准备中...")

        msg = f"PDF 识别进度: {done}/{total} 页 ({pct:.0f}%)"
        if snap["queue_pending"] > 0 or snap["queue_running"] > 0:
            msg += f" | 排队 {snap['queue_pending']} 张, 识别中 {snap['queue_running']} 张"
        elapsed = snap["elapsed"]
        if elapsed > 0 and done > 0:
            speed = done / elapsed
            remain = (total - done) / speed if speed > 0 else 0
            if remain > 60:
                msg += f" | 预计还需 {remain/60:.0f} 分钟"
            elif remain > 0:
                msg += f" | 预计还需 {remain:.0f} 秒"
        return msg

    def _video_friendly(self, snap: dict) -> str:
        phase_id = snap["current_phase"]
        phases = snap["phases"]
        if not phase_id or phase_id not in phases:
            return snap.get("status_message", "准备中...")

        phase = phases[phase_id]
        phase_names = {
            "phase1": "音频提取",
            "phase2": "智能抽帧",
            "phase3": "完整帧缩放",
            "phase4": "大模型识别",
            "phase5": "语音识别",
            "phase4_hotwords": "提取热词",
        }
        name = phase_names.get(phase_id, phase["name"])

        if phase["total"] > 0:
            msg = f"阶段: {name} — {phase['current']}/{phase['total']}"
            if phase["percent"] > 0:
                msg += f" ({phase['percent']:.0f}%)"
        else:
            msg = f"阶段: {name}"

        desc = phase.get("description", "")
        if desc:
            msg += f" | {desc}"

        # 已完成阶段摘要
        done_phases = [
            f"{phases[p]['name']}({phases[p]['elapsed']:.0f}s)"
            for p in phases if phases[p]["is_done"]
        ]
        if done_phases:
            msg += f" | 已完成: {', '.join(done_phases)}"

        return msg
