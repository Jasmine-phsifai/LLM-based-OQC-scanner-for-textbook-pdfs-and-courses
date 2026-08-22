"""
增量 Markdown 写入器 — 原子化存储，支持乱序插入。

在识别过程中实时将结果写入 MD 文件。
由于并行任务完成顺序不确定，使用有序槽位确保最终输出有序。
"""

from __future__ import annotations

import hashlib
import os
import threading
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_COMPATIBLE_TEMP_PATH_CHARS = 240


class IncrementalMDWriter:
    """线程安全的增量 Markdown 写入器。

    用法:
        writer = IncrementalMDWriter("output.md", total_slots=80)
        # 并行任务完成后，按索引写入
        writer.write_slot(5, "<!-- meta:page number=6 -->\\n\\n内容...")
        writer.write_slot(2, "<!-- meta:page number=3 -->\\n\\n内容...")
        # 随时可调用 flush 写入文件（自动排序）
        writer.flush()
        # 最终完成
        writer.finalize()
    """

    def __init__(self, output_path: str, total_slots: int, truncate: bool = True):
        self._output_path = output_path
        self._total_slots = total_slots
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._io_lock = threading.Lock()
        self._slots: dict[int, str] = {}
        self._flushed_up_to: int = -1  # 已连续写入到的最大索引
        self._flush_dirty: bool = False  # 增量写入曾失败，finalize 需全量覆写
        self._append_inflight: bool = False
        self._flush_in_progress: bool = False

        # 确保输出目录存在
        os.makedirs(os.path.dirname(self._output_path) or ".", exist_ok=True)

        # 仅在非续传场景清空文件；续传时由 seed_slots + flush 安全覆盖
        if truncate:
            with open(self._output_path, "w", encoding="utf-8") as f:
                f.write("")

    def write_slot(self, index: int, content: str):
        """写入指定槽位的内容。线程安全。"""
        with self._cond:
            self._slots[index] = content
            logger.debug("[MD] 写入槽位 %d/%d", index + 1, self._total_slots)
            self._cond.notify_all()

        # 尝试增量 flush
        self._try_incremental_flush()

    def seed_slots(self, slots: dict[int, str], rewrite: bool = True):
        """恢复已有槽位内容，用于断点续传。"""
        if not slots:
            return
        with self._cond:
            self._slots.update(slots)
            next_idx = -1
            while next_idx + 1 in self._slots:
                next_idx += 1
            self._flushed_up_to = next_idx
            self._cond.notify_all()
        if rewrite:
            self.flush()

    def _collect_contiguous_slots_locked(self) -> list[tuple[int, str]]:
        """在持锁状态下收集从 _flushed_up_to+1 开始的连续槽位。"""
        next_idx = self._flushed_up_to + 1
        to_write = []
        while next_idx in self._slots:
            to_write.append((next_idx, self._slots[next_idx]))
            next_idx += 1
        return to_write

    def _try_incremental_flush(self):
        """如果有新的连续槽位可写入，追加到文件。

        设计目标：
        1. 文件 I/O 不阻塞写槽位的状态更新。
        2. 任意时刻最多只有一个增量 append 在飞行中。
        3. append 失败后停止后续增量写，等待 flush/finalize 做全量覆写修正。
        """
        while True:
            with self._cond:
                if self._flush_dirty or self._append_inflight or self._flush_in_progress:
                    return

                to_write = self._collect_contiguous_slots_locked()
                if not to_write:
                    return

                end_idx = to_write[-1][0]
                self._append_inflight = True

            try:
                with self._io_lock:
                    with open(self._output_path, "a", encoding="utf-8") as f:
                        for idx, content in to_write:
                            if idx > 0:
                                f.write("\n\n")
                            f.write(content.strip())
            except OSError as e:
                logger.error("[MD] 增量写入失败（flush/finalize 时将全量覆写修正）: %s", e)
                with self._cond:
                    self._append_inflight = False
                    self._flush_dirty = True
                    self._cond.notify_all()
                return

            with self._cond:
                self._append_inflight = False
                self._flushed_up_to = end_idx
                self._cond.notify_all()

            logger.debug("[MD] 增量写入到槽位 %d", end_idx)

    def flush(self):
        """将所有已有内容按顺序写入文件（全量刷新）。"""
        with self._cond:
            self._flush_in_progress = True
            while self._append_inflight:
                self._cond.wait()

            if not self._slots:
                self._flush_in_progress = False
                self._cond.notify_all()
                return

            sorted_indices = sorted(self._slots.keys())
            parts = [self._slots[i].strip() for i in sorted_indices]

            contiguous = -1
            while contiguous + 1 in self._slots:
                contiguous += 1

        try:
            with self._io_lock:
                tmp_path = self._temp_path()
                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.write("\n\n".join(parts))
                os.replace(tmp_path, self._output_path)
        except OSError as e:
            logger.error("[MD] 全量刷新失败: %s", e)
            with self._cond:
                self._flush_dirty = True
                self._flush_in_progress = False
                self._cond.notify_all()
            return

        with self._cond:
            self._flushed_up_to = contiguous
            self._flush_dirty = False
            self._flush_in_progress = False
            self._cond.notify_all()

        logger.info("[MD] 全量刷新: %d/%d 槽位", len(parts), self._total_slots)
        self._try_incremental_flush()

    def _temp_path(self) -> Path:
        output = Path(self._output_path)
        candidate = output.with_name(output.name + ".tmp")
        if self._is_compatible_temp_path(candidate):
            return candidate

        digest = hashlib.sha1(str(output).encode("utf-8", errors="surrogatepass")).hexdigest()[:12]
        return output.with_name(f".ocrllm-{digest}.tmp")

    @staticmethod
    def _is_compatible_temp_path(path: Path) -> bool:
        return len(str(path.resolve(strict=False))) <= _MAX_COMPATIBLE_TEMP_PATH_CHARS

    def finalize(self):
        """最终写入：确保所有槽位内容有序写入文件。

        无论增量写入是否曾失败，finalize 总是做全量覆写以保证最终一致性。
        """
        self.flush()
        filled = len(self._slots)
        logger.info("[MD] 最终写入完成: %d/%d 槽位已填充 -> %s",
                    filled, self._total_slots, self._output_path)

    @property
    def filled_count(self) -> int:
        """已写入内容的槽位数量。"""
        with self._lock:
            return len(self._slots)

    @property
    def is_complete(self) -> bool:
        """所有槽位是否已填充完成。"""
        with self._lock:
            return len(self._slots) >= self._total_slots

    def get_filled_indices(self) -> set[int]:
        """已完成的槽位索引集合。"""
        with self._lock:
            return set(self._slots.keys())
