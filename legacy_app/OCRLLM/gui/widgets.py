"""
可复用 GUI 组件。
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import (
    QLineEdit, QFileDialog, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMessageBox, QWidget, QTextEdit,
)
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QFont
from PyQt5.QtCore import Qt, QSettings

from OCRLLM.core.checkpoint import Checkpoint, CheckpointManager


class PromptEditorDialog(QDialog):
    """Edit a prompt and choose temporary or permanent storage."""

    TEMPORARY = "temporary"
    PERMANENT = "permanent"
    RESET = "reset"

    def __init__(self, title: str, prompt_text: str, default_text: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._action: str | None = None
        self._default_text = default_text
        self.setWindowTitle(title)
        self.resize(820, 560)

        layout = QVBoxLayout(self)
        self._editor = QTextEdit()
        self._editor.setFont(QFont("Consolas", 9))
        self._editor.setPlainText(prompt_text)
        layout.addWidget(self._editor, stretch=1)

        btn_row = QHBoxLayout()
        reset_btn = QPushButton("恢复默认")
        reset_btn.clicked.connect(self._reset_to_default)
        btn_row.addWidget(reset_btn)

        btn_row.addStretch()
        temp_btn = QPushButton("临时保存")
        temp_btn.clicked.connect(self._save_temporary)
        btn_row.addWidget(temp_btn)

        permanent_btn = QPushButton("永久保存")
        permanent_btn.clicked.connect(self._save_permanent)
        btn_row.addWidget(permanent_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    @property
    def action(self) -> str | None:
        return self._action

    @property
    def prompt_text(self) -> str:
        return self._editor.toPlainText()

    def _reset_to_default(self):
        self._action = self.RESET
        self.accept()

    def _save_temporary(self):
        self._action = self.TEMPORARY
        self.accept()

    def _save_permanent(self):
        self._action = self.PERMANENT
        self.accept()


class PromptButton(QPushButton):
    """Button entry point for a prompt editor with one-shot temporary saves."""

    _SETTINGS_ORG = "OCRLLM"
    _SETTINGS_APP = "QCR"

    def __init__(self, label: str, settings_key: str, default_text: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._label = label
        self._settings_key = f"prompts/{settings_key}"
        self._default_text = default_text
        self._settings = QSettings(self._SETTINGS_ORG, self._SETTINGS_APP)
        saved = self._settings.value(self._settings_key, type=str)
        self._permanent_text = saved if saved else default_text
        self._current_text = self._permanent_text
        self._temporary = False
        self.clicked.connect(self.open_editor)
        self._refresh_label()

    def prompt_text(self) -> str:
        return self._current_text.strip()

    def reset_to_default(self):
        self._settings.remove(self._settings_key)
        self._settings.sync()
        self._permanent_text = self._default_text
        self._current_text = self._default_text
        self._temporary = False
        self._refresh_label()

    def consume_temporary(self):
        if not self._temporary:
            return
        self._current_text = self._permanent_text
        self._temporary = False
        self._refresh_label()

    def open_editor(self):
        dlg = PromptEditorDialog(
            f"自定义提示词 - {self._label}",
            self._current_text,
            self._default_text,
            self,
        )
        if dlg.exec_() != QDialog.Accepted:
            return

        if dlg.action == PromptEditorDialog.RESET:
            self.reset_to_default()
            return

        text = dlg.prompt_text
        if dlg.action == PromptEditorDialog.PERMANENT:
            self._permanent_text = text
            self._current_text = text
            self._temporary = False
            self._settings.setValue(self._settings_key, text)
            self._settings.sync()
        elif dlg.action == PromptEditorDialog.TEMPORARY:
            self._current_text = text
            self._temporary = True
        self._refresh_label()

    def _refresh_label(self):
        suffix = "临时" if self._temporary else (
            "永久" if self._permanent_text.strip() != self._default_text.strip() else "默认"
        )
        self.setText(f"自定义提示词 ({suffix})")


class FileInput(QLineEdit):
    """支持拖放的文件路径输入框。"""

    def __init__(self, accept_exts: list[str] = None, multi: bool = False,
                 placeholder: str = "", parent=None):
        super().__init__(parent)
        self._accept_exts = [e.lower().lstrip('.') for e in (accept_exts or [])]
        self._multi = multi
        self.setAcceptDrops(True)
        if placeholder:
            self.setPlaceholderText(placeholder)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖放进入事件：接受含 URL 的拖放数据。"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        """拖放释放事件：提取文件路径并过滤扩展名后填入输入框。"""
        urls = event.mimeData().urls()
        paths = []
        for url in urls:
            p = url.toLocalFile()
            if not p:
                continue
            if self._accept_exts:
                ext = os.path.splitext(p)[1].lower().lstrip('.')
                if ext not in self._accept_exts:
                    continue
            paths.append(p)
        if paths:
            if self._multi:
                self.setText(join_paths_text(split_paths_text(self.text()) + paths))
            else:
                self.setText(paths[0])


def split_paths_text(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(";") if part.strip()]


def join_paths_text(paths: list[str]) -> str:
    ordered = list(dict.fromkeys(path.strip() for path in paths if path and path.strip()))
    return ";".join(ordered)


def browse_file(parent, caption: str, filter_str: str, line_edit: QLineEdit):
    """打开单文件选择对话框，选中后填入指定输入框。

    Args:
        parent: 父控件。
        caption: 对话框标题。
        filter_str: 文件过滤器字符串。
        line_edit: 目标输入框。
    """
    start_dir = os.path.dirname(line_edit.text().strip()) if line_edit.text().strip() else ""
    path, _ = QFileDialog.getOpenFileName(parent, caption, start_dir, filter_str)
    if path:
        line_edit.setText(path)


def browse_files(parent, caption: str, filter_str: str, line_edit: QLineEdit):
    """打开多文件选择对话框，选中后以分号分隔填入输入框。

    Args:
        parent: 父控件。
        caption: 对话框标题。
        filter_str: 文件过滤器字符串。
        line_edit: 目标输入框。
    """
    existing = line_edit.text().strip()
    start_dir = os.path.dirname(split_paths_text(existing)[0]) if existing else ""
    paths, _ = QFileDialog.getOpenFileNames(parent, caption, start_dir, filter_str)
    if paths:
        line_edit.setText(join_paths_text(split_paths_text(existing) + paths))


class IncompleteTasksDialog(QDialog):
    """管理所有未完成任务的对话框。

    用户可以浏览、继续、或取消任意未完成任务；取消不会删除已生成的结果。
    """

    def __init__(self, checkpoint_mgr: CheckpointManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._mgr = checkpoint_mgr
        self._selected_checkpoint: Optional[Checkpoint] = None
        self._selected_checkpoints: list[Checkpoint] = []
        self._action: Optional[str] = None  # "resume" or "cancel"
        self._init_ui()
        self._refresh()

    @property
    def selected_checkpoint(self) -> Optional[Checkpoint]:
        return self._selected_checkpoint

    @property
    def selected_checkpoints(self) -> list[Checkpoint]:
        return list(self._selected_checkpoints)

    @property
    def action(self) -> Optional[str]:
        return self._action

    def _init_ui(self):
        self.setWindowTitle("未完成任务管理")
        self.setMinimumSize(750, 400)
        self.resize(850, 480)

        layout = QVBoxLayout(self)

        hint = QLabel("以下是所有未完成的识别任务。可以多选后批量继续，或取消不需要继续的任务（保留已生成的识别结果）。")
        hint.setWordWrap(True)
        hint.setFont(QFont("", 9))
        layout.addWidget(hint)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["类型", "源文件", "进度", "输出位置", "更新时间"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table, stretch=1)

        btn_row = QHBoxLayout()
        self._select_all_btn = QPushButton("全选")
        self._select_all_btn.clicked.connect(self._select_all)
        btn_row.addWidget(self._select_all_btn)

        self._resume_btn = QPushButton("⏩ 继续选中任务")
        self._resume_btn.clicked.connect(self._on_resume)
        btn_row.addWidget(self._resume_btn)

        self._cancel_btn = QPushButton("⏹ 取消选中任务（保留结果）")
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._cancel_btn)

        self._cancel_all_btn = QPushButton("⏹ 取消全部（保留结果）")
        self._cancel_all_btn.clicked.connect(self._on_cancel_all)
        btn_row.addWidget(self._cancel_all_btn)

        btn_row.addStretch()
        self._close_btn = QPushButton("关闭")
        self._close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._close_btn)
        layout.addLayout(btn_row)

    def _refresh(self):
        self._checkpoints = self._mgr.list_incomplete()
        self._table.setRowCount(len(self._checkpoints))
        for row, cp in enumerate(self._checkpoints):
            type_text = (
                "PDF" if cp.task_type == "pdf"
                else "视频" if cp.task_type == "video"
                else "音频" if cp.task_type == "audio"
                else cp.task_type
            )
            src_name = Path(cp.source_path).name
            updated = datetime.fromtimestamp(cp.updated_at).strftime("%m-%d %H:%M")
            output_short = cp.output_path

            self._table.setItem(row, 0, QTableWidgetItem(type_text))
            self._table.setItem(row, 1, QTableWidgetItem(src_name))
            self._table.setItem(row, 2, QTableWidgetItem(cp.progress_text))
            self._table.setItem(row, 3, QTableWidgetItem(output_short))
            self._table.setItem(row, 4, QTableWidgetItem(updated))

        has_items = len(self._checkpoints) > 0
        self._select_all_btn.setEnabled(has_items)
        self._resume_btn.setEnabled(has_items)
        self._cancel_btn.setEnabled(has_items)
        self._cancel_all_btn.setEnabled(has_items)

        if has_items:
            self._table.selectRow(0)

    def _select_all(self):
        self._table.selectAll()

    def _get_selected_cps(self) -> list[Checkpoint]:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return []
        selected = []
        for row in sorted({idx.row() for idx in rows}):
            if 0 <= row < len(self._checkpoints):
                selected.append(self._checkpoints[row])
        return selected

    def _get_selected_cp(self) -> Optional[Checkpoint]:
        selected = self._get_selected_cps()
        return selected[0] if selected else None

    def _on_resume(self):
        checkpoints = self._get_selected_cps()
        if not checkpoints:
            QMessageBox.information(self, "提示", "请先选择任务")
            return
        self._selected_checkpoints = checkpoints
        self._selected_checkpoint = checkpoints[0]
        self._action = "resume"
        self.accept()

    def _on_cancel(self):
        checkpoints = self._get_selected_cps()
        if not checkpoints:
            QMessageBox.information(self, "提示", "请先选择任务")
            return
        if len(checkpoints) == 1:
            msg = f"确定取消任务 \"{Path(checkpoints[0].source_path).name}\" 吗？\n\n已生成的识别结果会保留。"
        else:
            msg = f"确定取消选中的 {len(checkpoints)} 个未完成任务吗？\n\n已生成的识别结果会保留。"
        reply = QMessageBox.question(
            self, "确认取消",
            msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        for cp in checkpoints:
            self._mgr.cancel(cp)
        self._refresh()

    def _on_cancel_all(self):
        if not self._checkpoints:
            return
        reply = QMessageBox.question(
            self, "确认取消全部",
            f"确定取消全部 {len(self._checkpoints)} 个未完成任务吗？\n\n已生成的识别结果会保留。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        for cp in list(self._checkpoints):
            self._mgr.cancel(cp)
        self._refresh()
