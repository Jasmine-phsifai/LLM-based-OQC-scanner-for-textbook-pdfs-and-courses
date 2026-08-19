"""
断点续传 — 保存/恢复长任务的检查点状态。

当 802 页 PDF 在第 600 页断开时，下次启动可从 601 页继续。
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CHECKPOINT_DIR_NAME = ".checkpoints"


def _checkpoint_dir(base_dir: str) -> str:
    d = os.path.join(base_dir, CHECKPOINT_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def _safe_filename(name: str) -> str:
    """文件名安全化"""
    return "".join(c if c.isalnum() or c in ("_", "-", ".") else "_" for c in name)


class Checkpoint:
    """单个任务的检查点。"""

    def __init__(
        self,
        task_type: str,
        source_path: str,
        output_path: str,
        total_items: int,
        completed_indices: set[int] = None,
        extra: dict = None,
    ):
        self.task_type = task_type
        self.source_path = source_path
        self.output_path = output_path
        self.total_items = total_items
        self.completed_indices = completed_indices or set()
        self.extra = extra or {}
        self.created_at = time.time()
        self.updated_at = time.time()

    @property
    def remaining_indices(self) -> list[int]:
        """尚未完成的条目索引列表（升序）。"""
        all_indices = set(range(self.total_items))
        return sorted(all_indices - self.completed_indices)

    @property
    def is_complete(self) -> bool:
        """所有条目是否已完成。"""
        return len(self.completed_indices) >= self.total_items

    @property
    def progress_text(self) -> str:
        """人类可读的进度文本，如 ``600/802 (75%)``。"""
        done = len(self.completed_indices)
        pct = done / self.total_items * 100 if self.total_items > 0 else 0.0
        return f"{done}/{self.total_items} ({pct:.0f}%)"

    @property
    def resume_key(self) -> tuple[str, str]:
        """稳定标识同一个检查点任务。"""
        return self.task_type, os.path.abspath(self.source_path)

    def mark_completed(self, index: int):
        """标记某个条目为已完成。

        Args:
            index: 条目索引。
        """
        self.completed_indices.add(index)
        self.updated_at = time.time()

    def replace_completed(self, indices: set[int] | list[int]):
        """用新的已完成索引集合替换当前状态。"""
        self.completed_indices = set(indices)
        self.updated_at = time.time()

    def is_compatible(
        self,
        *,
        total_items: int | None = None,
        output_path: str | None = None,
        expected_extra: dict | None = None,
    ) -> bool:
        """判断检查点是否与当前运行参数兼容。"""
        if total_items is not None and self.total_items != total_items:
            return False
        if output_path is not None and os.path.abspath(self.output_path) != os.path.abspath(output_path):
            return False
        if expected_extra:
            for key, value in expected_extra.items():
                if self.extra.get(key) != value:
                    return False
        return True

    def to_dict(self) -> dict:
        """序列化为可 JSON 持久化的字典。

        Returns:
            检查点状态字典。
        """
        return {
            "task_type": self.task_type,
            "source_path": self.source_path,
            "output_path": self.output_path,
            "total_items": self.total_items,
            "completed_indices": sorted(self.completed_indices),
            "extra": self.extra,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Checkpoint:
        """从字典反序列化为 Checkpoint 实例。

        Args:
            data: 由 ``to_dict()`` 生成的字典。

        Returns:
            恢复的 Checkpoint 实例。
        """
        cp = cls(
            task_type=data["task_type"],
            source_path=data["source_path"],
            output_path=data["output_path"],
            total_items=data["total_items"],
            completed_indices=set(data.get("completed_indices", [])),
            extra=data.get("extra", {}),
        )
        cp.created_at = data.get("created_at", time.time())
        cp.updated_at = data.get("updated_at", time.time())
        return cp


class CheckpointManager:
    """管理多个任务的检查点存储和恢复。"""

    def __init__(self, base_dir: str):
        self._base_dir = base_dir
        self._cp_dir = _checkpoint_dir(base_dir)
        self._save_lock = threading.Lock()

    def _cp_path(self, task_type: str, source_path: str) -> str:
        stem = _safe_filename(Path(source_path).stem)
        source_key = hashlib.sha1(os.path.abspath(source_path).encode("utf-8")).hexdigest()[:10]
        return os.path.join(self._cp_dir, f"{task_type}_{stem}_{source_key}.json")

    def save(self, checkpoint: Checkpoint):
        """保存检查点到磁盘。"""
        path = self._cp_path(checkpoint.task_type, checkpoint.source_path)
        data = checkpoint.to_dict()
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
            logger.debug("[CP] 保存: %s (%s)", path, checkpoint.progress_text)
        except OSError as e:
            logger.error("[CP] 保存失败: %s", e)

    def load(self, task_type: str, source_path: str) -> Optional[Checkpoint]:
        """加载检查点（如果存在且未完成）。"""
        path = self._cp_path(task_type, source_path)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cp = Checkpoint.from_dict(data)
            if cp.is_complete:
                self.remove(task_type, source_path)
                return None
            # 验证源文件仍然存在
            if not os.path.exists(cp.source_path):
                logger.warning("[CP] 源文件不存在，删除检查点: %s", cp.source_path)
                self.remove(task_type, source_path)
                return None
            logger.info("[CP] 找到检查点: %s → %s", path, cp.progress_text)
            return cp
        except (json.JSONDecodeError, KeyError, TypeError, OSError) as e:
            logger.warning("[CP] 加载失败，删除: %s (%s)", path, e)
            self.remove(task_type, source_path)
            return None

    def remove(self, task_type: str, source_path: str):
        """删除检查点。"""
        path = self._cp_path(task_type, source_path)
        if not os.path.exists(path):
            logger.debug("[CP] remove no-op (file not found): %s", path)
            return
        try:
            os.remove(path)
            logger.info("[CP] 已删除检查点: %s", path)
        except OSError as e:
            # 历史上这里直接 swallow，导致 "成功任务的 checkpoint 实际未被删" 这种诡异 bug
            # 排查无门。改成显式警告。
            logger.warning("[CP] 删除检查点失败 (将留在磁盘上，下次启动会被列出): %s — %s", path, e)

    def list_incomplete(self) -> list[Checkpoint]:
        """列出所有真正未完成的检查点。

        会自动过滤并清理"实际已经完成但 checkpoint 没被删掉"的脏数据：
          - video: 若 output_path 下板书识别 .md 已存在且非空，且全部用户选择的 phase 已记录
          - pdf:   若 output_path .md 已存在且 completed_indices == total_items
        过滤掉的会顺手清掉磁盘上的 checkpoint 文件，避免下次还显示。
        """
        results = []
        if not os.path.isdir(self._cp_dir):
            return results
        for fname in os.listdir(self._cp_dir):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(self._cp_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cp = Checkpoint.from_dict(data)
            except (json.JSONDecodeError, KeyError, TypeError, OSError) as e:
                logger.warning("[CP] 跳过损坏的检查点 %s: %s", path, e)
                continue
            if not os.path.exists(cp.source_path):
                logger.info("[CP] 源文件已不存在，清理 checkpoint: %s", path)
                self._unlink_silent(path)
                continue
            if cp.is_complete:
                logger.info("[CP] checkpoint 显示已完成 (%s)，清理: %s", cp.progress_text, path)
                self._unlink_silent(path)
                continue
            if self._looks_actually_done(cp):
                logger.info(
                    "[CP] 检测到任务已实际完成 (output 已存在且齐全)，清理脏 checkpoint: %s",
                    path,
                )
                self._unlink_silent(path)
                continue
            results.append(cp)
        results.sort(key=lambda cp: cp.updated_at, reverse=True)
        return results

    def _unlink_silent(self, path: str) -> None:
        try:
            os.remove(path)
        except OSError as e:
            logger.warning("[CP] 清理脏 checkpoint 失败 %s: %s", path, e)

    @staticmethod
    def _file_nonempty(path: str) -> bool:
        try:
            return os.path.isfile(path) and os.path.getsize(path) > 0
        except OSError:
            return False

    def _looks_actually_done(self, cp: "Checkpoint") -> bool:
        """启发式：output 文件已经齐全 → 这个 checkpoint 是脏数据，应丢弃。"""
        try:
            if cp.task_type == "pdf":
                # PDF 输出是单个 .md 文件。但部分失败的任务也会写出非空 md
                # （失败槽位含占位注释），所以必须同时要求 checkpoint 自身记录完整，
                # 否则失败任务的 checkpoint 会在这里被误删，断点续传入口消失。
                return cp.is_complete and self._file_nonempty(cp.output_path)
            if cp.task_type == "video":
                stem = (cp.extra or {}).get("stem")
                if not stem:
                    return False
                output_dir = cp.output_path
                board_md = os.path.join(output_dir, f"{stem}_板书识别.md")
                phases = (cp.extra or {}).get("phases") or []
                # 板书识别 md 存在且非空，是核心完成标志
                if not self._file_nonempty(board_md):
                    return False
                # 若用户选了 phase 5 (语音识别)，再确认转写 md 也存在
                if 5 in phases:
                    transcript = os.path.join(output_dir, f"{stem}_录音识别.md")
                    if not self._file_nonempty(transcript):
                        return False
                return True
            if cp.task_type == "audio":
                return cp.is_complete and self._file_nonempty(cp.output_path)
        except Exception as e:
            logger.debug("[CP] _looks_actually_done 检查失败 (%s)，按未完成处理: %s", cp.source_path, e)
        return False

    def select_incomplete(self, preferred_key: tuple[str, str] | None = None) -> Optional[Checkpoint]:
        """返回首选未完成检查点；若首选不存在，则返回最新的一个。"""
        incomplete = self.list_incomplete()
        if not incomplete:
            return None
        if preferred_key is not None:
            for checkpoint in incomplete:
                if checkpoint.resume_key == preferred_key:
                    return checkpoint
        return incomplete[0]

    def cancel(self, checkpoint: Checkpoint):
        """取消检查点，但保留所有已经生成的输出。"""
        logger.info(
            "[CP] 取消任务，保留已生成输出: %s -> %s",
            checkpoint.source_path,
            checkpoint.output_path,
        )
        self.remove(checkpoint.task_type, checkpoint.source_path)

    def remove_with_artifacts(self, checkpoint: Checkpoint, *, delete_outputs: bool = False):
        """删除检查点；仅显式要求时才删除输出。"""
        if not delete_outputs:
            self.cancel(checkpoint)
            return

        import shutil

        output_path = checkpoint.output_path
        task_type = checkpoint.task_type

        if task_type == "video" and os.path.isdir(output_path):
            try:
                shutil.rmtree(output_path)
                logger.info("[CP] 已清理视频输出目录: %s", output_path)
            except OSError as e:
                logger.warning("[CP] 清理视频输出目录失败: %s", e)

            # 也清理 temp 下的 debug 目录
            stem = checkpoint.extra.get("stem", "")
            if stem:
                temp_base = os.path.join(os.path.dirname(self._base_dir), "temp")
                if os.path.isdir(temp_base):
                    for entry in os.listdir(temp_base):
                        if entry.startswith(f"video_debug_{stem[:30]}"):
                            debug_path = os.path.join(temp_base, entry)
                            try:
                                shutil.rmtree(debug_path)
                                logger.info("[CP] 已清理视频调试目录: %s", debug_path)
                            except OSError as e:
                                logger.warning("[CP] 清理调试目录失败: %s", e)

        elif task_type == "pdf" and os.path.isfile(output_path):
            try:
                os.remove(output_path)
                logger.info("[CP] 已清理 PDF 输出文件: %s", output_path)
            except OSError as e:
                logger.warning("[CP] 清理 PDF 输出失败: %s", e)

        elif task_type == "audio" and os.path.isfile(output_path):
            try:
                os.remove(output_path)
                logger.info("[CP] 已清理音频输出文件: %s", output_path)
            except OSError as e:
                logger.warning("[CP] 清理音频输出失败: %s", e)

        self.remove(checkpoint.task_type, checkpoint.source_path)

    def save_incremental(self, checkpoint: Checkpoint, index: int, result: str = ""):
        """标记一项完成并保存（高频调用，只保存索引不保存结果内容）。"""
        with self._save_lock:
            checkpoint.mark_completed(index)
            self.save(checkpoint)
