"""
模型选择对话框 — 替代普通下拉框，规模化处理大量模型条目。

UI 元素：
  · 顶部：搜索框（即时过滤 name / label / kind）
  · 中部：分类 chip（全部 / 仅免费额度 / 视觉只看 vlm/ocr/omni 等 / 音频只看 asr_long 等）
  · 列表：表格视图，列 = [模型 ID | 类型 | 张数/时长 | 免费 | 备注]
  · 底部：自定义模型输入框 + "测试并添加..." 按钮
  · 主按钮：选中后回填到调用方

采用 model_catalog 提供的 builtin + user 列表。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QDialog,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QRadioButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from OCRLLM.core import model_catalog
from OCRLLM.core.model_catalog import AudioModel, VisionModel

# Shared with the picker's own "fetch now" button; kept separate from
# settings_dialog's executor since this module must not import that one.
_PICKER_FETCH_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ocrllm-picker-fetch")


_VISION_KIND_FILTERS = [
    ("全部",  None),
    ("仅 OCR (qwen-vl-ocr)", "ocr"),
    ("Qwen-VL 通用视觉", "vlm"),
    ("通用大模型 (含视觉)", "general"),
    ("Omni 全模态", "omni"),
]

_AUDIO_KIND_FILTERS = [
    ("全部", None),
    ("长录音 asr_long (录课首选)", "asr_long"),
    ("短录音 asr_short", "asr_short"),
    ("Omni 短音频聊天", "omni_audio"),
]


class ModelPickerDialog(QDialog):
    """带搜索/过滤/自定义+测试入口的模型选择对话框。"""

    def __init__(
        self,
        parent: QWidget,
        *,
        kind: str,        # "vision" 或 "audio"
        current_name: str = "",
        on_validate_custom=None,    # callable(name) -> bool, 用于测试自定义模型
        on_fetch_live: Optional[Callable[[], None]] = None,  # 无参真实拉取，失败时 raise
    ):
        super().__init__(parent)
        self._kind = kind
        self._on_validate_custom = on_validate_custom
        self._on_fetch_live = on_fetch_live
        self._selected_name: str = current_name
        self._init_ui()
        self._reload_table()
        self._select_row_by_name(current_name)

    # ---- 公共属性 ----

    @property
    def selected_model_name(self) -> str:
        return self._selected_name

    # ---- UI ----

    def _init_ui(self):
        self.setWindowTitle("选择视觉模型" if self._kind == "vision" else "选择音频模型")
        self.setMinimumSize(960, 640)
        self.resize(1080, 720)
        self.setSizeGripEnabled(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # 搜索框
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("🔍 搜索:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("输入模型名 / 描述关键词，如 vl-ocr, omni, paraformer ...")
        self._search.textChanged.connect(self._reload_table)
        search_row.addWidget(self._search, stretch=1)
        self._only_free = QCheckBox("仅显示【免费额度】")
        self._only_free.setChecked(True)
        self._only_free.toggled.connect(self._reload_table)
        search_row.addWidget(self._only_free)
        self._fetch_live_btn = QPushButton("🔄 拉取最新模型")
        self._fetch_live_btn.setToolTip("实时调用 /models 获取当前账号真实模型列表，不是静态清单")
        self._fetch_live_btn.clicked.connect(self._on_fetch_live_clicked)
        self._fetch_live_btn.setVisible(self._on_fetch_live is not None)
        search_row.addWidget(self._fetch_live_btn)
        layout.addLayout(search_row)

        # 分类 radio (横向 chip)
        chip_row = QHBoxLayout()
        chip_row.addWidget(QLabel("类型过滤:"))
        self._kind_group = QButtonGroup(self)
        filters = _VISION_KIND_FILTERS if self._kind == "vision" else _AUDIO_KIND_FILTERS
        for idx, (text, _) in enumerate(filters):
            r = QRadioButton(text)
            if idx == 0:
                r.setChecked(True)
            r.toggled.connect(self._reload_table)
            self._kind_group.addButton(r, idx)
            chip_row.addWidget(r)
        chip_row.addStretch()
        layout.addLayout(chip_row)

        # 表格
        if self._kind == "vision":
            headers = ["模型 ID", "类型", "图片张数", "免费", "描述"]
        else:
            headers = ["模型 ID", "类型", "时长上限", "免费", "描述"]
        self._table = QTableWidget()
        self._table.setColumnCount(len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self._table.itemSelectionChanged.connect(self._on_row_changed)
        self._table.doubleClicked.connect(lambda *_: self._on_ok())
        layout.addWidget(self._table, stretch=1)

        # 自定义模型行
        custom_row = QHBoxLayout()
        custom_row.addWidget(QLabel("自定义:"))
        self._custom_input = QLineEdit()
        self._custom_input.setPlaceholderText("输入未在列表中的模型 ID（如 deepseek-v4-flash-2025），点击右侧按钮真实测试")
        custom_row.addWidget(self._custom_input, stretch=1)
        self._test_btn = QPushButton("🧪 测试并添加")
        self._test_btn.setToolTip("会用真实 API 跑一次测试，通过后写入 user_models.json，下次仍可用。")
        self._test_btn.clicked.connect(self._on_validate_clicked)
        custom_row.addWidget(self._test_btn)
        layout.addLayout(custom_row)

        # 底部：当前选中 + OK / Cancel
        bottom_row = QHBoxLayout()
        self._selected_label = QLabel("未选中任何模型")
        self._selected_label.setFont(QFont("", 9, QFont.Bold))
        bottom_row.addWidget(self._selected_label, stretch=1)
        ok_btn = QPushButton("✅ 选中此模型")
        ok_btn.clicked.connect(self._on_ok)
        bottom_row.addWidget(ok_btn)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        bottom_row.addWidget(cancel_btn)
        layout.addLayout(bottom_row)

    # ---- 行为 ----

    def _on_fetch_live_clicked(self):
        if self._on_fetch_live is None:
            return
        self._fetch_live_btn.setEnabled(False)
        self._fetch_live_btn.setText("拉取中...")
        future = _PICKER_FETCH_EXECUTOR.submit(self._on_fetch_live)
        timer = QTimer(self)

        def _poll():
            if not future.done():
                return
            timer.stop()
            timer.deleteLater()
            self._fetch_live_btn.setEnabled(True)
            self._fetch_live_btn.setText("🔄 拉取最新模型")
            try:
                future.result()
            except Exception as exc:  # noqa: BLE001 - surfaced to the user
                QMessageBox.warning(self, "拉取失败", str(exc))
                return
            self._reload_table()
            QMessageBox.information(self, "拉取完成", "模型列表已根据当前账号实时更新。")

        timer.timeout.connect(_poll)
        timer.start(80)

    def _current_kind_filter(self) -> Optional[str]:
        idx = self._kind_group.checkedId()
        filters = _VISION_KIND_FILTERS if self._kind == "vision" else _AUDIO_KIND_FILTERS
        if 0 <= idx < len(filters):
            return filters[idx][1]
        return None

    def _all_models(self):
        if self._kind == "vision":
            return list(model_catalog.list_vision_models())
        return list(model_catalog.list_audio_models())

    def _matches_search(self, model, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        haystack = " ".join([model.name, getattr(model, "label", ""), getattr(model, "kind", ""),
                             getattr(model, "note", "")]).lower()
        return q in haystack

    def _matches_kind(self, model, kind_filter: Optional[str]) -> bool:
        if kind_filter is None:
            return True
        return getattr(model, "kind", "") == kind_filter

    def _reload_table(self):
        models = self._all_models()
        query = self._search.text()
        kind_filter = self._current_kind_filter()
        only_free = self._only_free.isChecked()

        rows = []
        for m in models:
            if only_free and not m.free_quota:
                continue
            if not self._matches_search(m, query):
                continue
            if not self._matches_kind(m, kind_filter):
                continue
            rows.append(m)

        self._table.setRowCount(len(rows))
        for r, m in enumerate(rows):
            self._table.setItem(r, 0, QTableWidgetItem(m.name))
            self._table.setItem(r, 1, QTableWidgetItem(getattr(m, "kind", "")))
            if isinstance(m, VisionModel):
                size_text = f"≤{m.max_images} 张" if m.max_images else "—"
            else:
                if m.max_seconds is None:
                    size_text = "—"
                elif m.max_seconds >= 3600:
                    size_text = f"≤{m.max_seconds // 3600} 小时"
                elif m.max_seconds >= 60:
                    size_text = f"≤{m.max_seconds // 60} 分钟"
                else:
                    size_text = f"≤{m.max_seconds} 秒"
            self._table.setItem(r, 2, QTableWidgetItem(size_text))
            self._table.setItem(r, 3, QTableWidgetItem("✅" if m.free_quota else ""))
            label = m.label.split("— ", 1)[-1] if "— " in m.label else m.label
            note = f"{label} · {m.note}" if m.note else label
            self._table.setItem(r, 4, QTableWidgetItem(note))
            for c in range(5):
                item = self._table.item(r, c)
                if item is not None:
                    item.setData(Qt.UserRole, m.name)

    def _on_row_changed(self):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        item = self._table.item(rows[0].row(), 0)
        if item is None:
            return
        self._selected_name = item.text()
        self._selected_label.setText(f"当前选中: {self._selected_name}")

    def _select_row_by_name(self, name: str):
        if not name:
            return
        for r in range(self._table.rowCount()):
            item = self._table.item(r, 0)
            if item is not None and item.text() == name:
                self._table.selectRow(r)
                return

    def _on_validate_clicked(self):
        name = self._custom_input.text().strip()
        if not name:
            QMessageBox.warning(self, "缺少模型名", "请先在自定义输入框里填一个模型 ID。")
            return
        if model_catalog.find_vision_model(name) if self._kind == "vision" else model_catalog.find_audio_model(name):
            QMessageBox.information(self, "已存在", f"{name} 已在清单中，直接选中即可。")
            self._select_row_by_name(name)
            return
        if self._on_validate_custom is None:
            QMessageBox.warning(self, "未提供测试入口",
                                "调用方未注册测试函数，无法验证自定义模型。")
            return
        ok = self._on_validate_custom(name)
        if ok:
            self._reload_table()
            self._select_row_by_name(name)
            self._custom_input.clear()

    def _on_ok(self):
        if not self._selected_name:
            QMessageBox.warning(self, "未选中", "请先在列表中选择一个模型。")
            return
        self.accept()
