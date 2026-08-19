"""
QCR 主窗口 — 顶层 GUI 入口。

关键架构改进（相比原版 main.py）:
  1. 不劫持 sys.stdout — 使用 GuiWorker + ProgressReporter
  2. 不在 worker 线程中修改全局 config — 通过 AppConfig 传参
  3. 每个 Tab 独立文件，职责清晰
  4. 进度追踪面板: 百分比进度条 + 阶段信息 + 队列状态
  5. 断点续传检查 + API 池配置
"""

from __future__ import annotations

import os
import sys
import logging
import subprocess
from pathlib import Path
from typing import Callable, Optional

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QGroupBox, QMessageBox,
    QStatusBar, QSpinBox, QLineEdit,
    QProgressBar, QCheckBox, QFrame,
)
from PyQt5.QtCore import Qt, QSettings, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont

from OCRLLM.config import AppConfig, normalize_google_ocr_vision_model
from OCRLLM.core import model_catalog
try:
    from OCRLLM.core.codex_vision import (
        CODEX_VISION_DEFAULT_MODEL,
        CODEX_VISION_DEFAULT_REASONING,
        migrate_stored_codex_vision_model,
        normalize_codex_vision_model,
    )
except ImportError:
    CODEX_VISION_DEFAULT_MODEL = "codex"
    CODEX_VISION_DEFAULT_REASONING = ""
    def migrate_stored_codex_vision_model(model: str | None) -> str:
        return normalize_codex_vision_model(model)

    def normalize_codex_vision_model(model: str | None) -> str:
        return (model or CODEX_VISION_DEFAULT_MODEL).strip()
from OCRLLM.core.utils import ensure_dir, setup_logging
from OCRLLM.core.progress_tracker import ProgressTracker
from OCRLLM.core.checkpoint import CheckpointManager
from OCRLLM.gui.worker import GuiWorker
from OCRLLM.gui.tabs.pdf_tab import PDFTab
from OCRLLM.gui.tabs.board_tab import BoardTab
from OCRLLM.gui.tabs.video_tab import VideoTab
from OCRLLM.gui.tabs.audio_tab import AudioTab
from OCRLLM.gui.tabs.social_tab import SocialTab
from OCRLLM.gui.widgets import IncompleteTasksDialog
from OCRLLM.processors.routing import InputRoutingError, route_input_paths

MONO_FONT = QFont("Consolas", 9)


class _QtLogHandler(logging.Handler):
    """线程安全的 logging → Qt 信号桥梁。"""
    def __init__(self, signal):
        super().__init__()
        self._signal = signal

    def emit(self, record):
        try:
            self._signal.emit(self.format(record))
        except (RuntimeError, AttributeError):
            pass


class QCRMainWindow(QMainWindow):
    """QCR 主窗口 — 集成 PDF、板书、视频、音频识别的多 Tab GUI。"""
    _log_signal = pyqtSignal(str)
    _free_tier_signal = pyqtSignal(str, str, str)  # (old_model, new_model, kind)
    _SETTINGS_ORG = "OCRLLM"
    _SETTINGS_APP = "QCR"

    def __init__(self, cfg: Optional[AppConfig] = None, window_index: int = 0):
        super().__init__()
        self._cfg = cfg or AppConfig()
        self._window_index = window_index
        self._worker = GuiWorker(parent=self)
        self._tracker = ProgressTracker()
        self._pending_resume = None
        self._close_after_worker = False
        self._allow_immediate_close = False
        self._suppress_worker_dialogs = False
        self._close_timeout_timer: Optional[QTimer] = None
        self._qt_log_handler = None
        self._log_buffer: list[str] = []
        self._log_flush_timer = QTimer(self)
        self._log_flush_timer.setSingleShot(True)
        self._log_flush_timer.timeout.connect(self._flush_log_buffer)
        self._settings = QSettings(self._SETTINGS_ORG, self._SETTINGS_APP)
        self._settings_save_timer = QTimer(self)
        self._settings_save_timer.setSingleShot(True)
        self._settings_save_timer.timeout.connect(self._persist_ui_settings)
        self._restoring_ui_settings = False
        self._log_window: QWidget | None = None

        ensure_dir(self._cfg.paths.output_dir)
        ensure_dir(self._cfg.paths.temp_dir)

        self._run_buttons: list[QPushButton] = []  # 运行按钮显式列表，用于禁用/启用
        self._free_tier_warned: set[tuple[str, str]] = set()  # 同次任务流程只弹一次同样的警告
        self._init_ui()
        self._free_tier_signal.connect(self._on_free_tier_switch)
        from OCRLLM.core.llm_client import set_free_tier_notifier
        set_free_tier_notifier(self._dispatch_free_tier_signal)
        self._restore_ui_settings()
        self._connect_settings_autosave()
        self._sync_api_from_ui()
        self._init_logging()
        self.destroyed.connect(lambda *_: self._cleanup_log_handler())
        self._connect_worker()
        self._check_resume_on_startup()

    def _get_cfg(self) -> AppConfig:
        return self._cfg

    def _get_tracker(self) -> ProgressTracker:
        return self._tracker

    def _get_output_in_place(self) -> bool:
        return self._output_in_place.isChecked()

    # ---- UI ----

    def _init_ui(self):
        self.setWindowTitle(f"QCR - 课程识别工具 [窗口 {self._window_index + 1}]")
        offset_x = 60 + (self._window_index % 6) * 40
        offset_y = 40 + (self._window_index % 6) * 30
        self.setGeometry(offset_x, offset_y, 1100, 900)
        self.setMinimumSize(950, 700)
        self.setAcceptDrops(True)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 5, 8, 5)
        self._build_header(layout)
        self._build_api_group(layout)
        self._build_spawn_row(layout)
        self._build_output_options(layout)
        self._build_progress_panel(layout)
        self._build_tabs_and_log(layout)

    def _build_header(self, layout: QVBoxLayout):

        title = QLabel("QCR - Qwen-powered Course Recognition")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("PDF · 板书 · 录课视频 · 语音识别 | 支持拖放文件 · 提示词编辑")
        subtitle.setFont(QFont("Segoe UI", 8))
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

    def _build_api_group(self, layout: QVBoxLayout):
        self._api_group = QGroupBox("API / 模型设置")
        api_layout = QHBoxLayout(self._api_group)
        api_layout.setContentsMargins(8, 6, 8, 6)

        self._api_summary = QLabel("")
        self._api_summary.setWordWrap(True)
        api_layout.addWidget(self._api_summary, stretch=1)

        self._api_status = QLabel("")
        api_layout.addWidget(self._api_status)

        btn_settings = QPushButton("⚙ 设置...")
        btn_settings.clicked.connect(self._open_settings_dialog)
        api_layout.addWidget(btn_settings)

        self._refresh_api_summary()
        layout.addWidget(self._api_group)

    def _build_spawn_row(self, layout: QVBoxLayout):
        spawn_row = QHBoxLayout()
        spawn_row.addStretch()
        spawn_row.addWidget(QLabel("多开窗口:"))
        self._spawn_spin = QSpinBox()
        self._spawn_spin.setRange(1, 9)
        self._spawn_spin.setValue(1)
        self._spawn_spin.setFixedWidth(50)
        spawn_row.addWidget(self._spawn_spin)
        btn_spawn = QPushButton("新开独立窗口")
        btn_spawn.clicked.connect(self._spawn_windows)
        spawn_row.addWidget(btn_spawn)
        layout.addLayout(spawn_row)

    def _build_output_options(self, layout: QVBoxLayout):
        out_row = QHBoxLayout()
        self._output_in_place = QCheckBox("在原位置输出结果（结果文件放在源文件同级目录）")
        self._output_in_place.setChecked(True)
        self._output_in_place.setToolTip("选中后，识别结果将保存到源文件所在目录，而非默认 output/ 文件夹")
        out_row.addWidget(self._output_in_place)
        out_row.addStretch()
        layout.addLayout(out_row)

    def _build_progress_panel(self, layout: QVBoxLayout):
        progress_frame = QFrame()
        progress_frame.setFrameStyle(QFrame.StyledPanel)
        progress_layout = QVBoxLayout(progress_frame)
        progress_layout.setContentsMargins(6, 4, 6, 4)

        pbar_row = QHBoxLayout()
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("%p%")
        self._progress_bar.setMinimumHeight(20)
        pbar_row.addWidget(self._progress_bar, stretch=1)
        self._log_button = QPushButton("运行日志")
        self._log_button.clicked.connect(self._show_log_window)
        pbar_row.addWidget(self._log_button)
        progress_layout.addLayout(pbar_row)

        self._progress_label = QLabel("就绪")
        self._progress_label.setWordWrap(True)
        self._progress_label.setFont(QFont("", 9))
        progress_layout.addWidget(self._progress_label)

        # 断点续传提示区
        self._resume_frame = QFrame()
        self._resume_frame.setVisible(False)
        resume_layout = QHBoxLayout(self._resume_frame)
        resume_layout.setContentsMargins(4, 2, 4, 2)
        self._resume_label = QLabel("")
        self._resume_label.setStyleSheet("color: #e67e22; font-weight: bold;")
        resume_layout.addWidget(self._resume_label, stretch=1)
        self._resume_btn = QPushButton("⏩ 继续任务")
        self._resume_btn.setProperty("qcr_run_button", True)
        self._resume_btn.clicked.connect(self._on_resume_clicked)
        resume_layout.addWidget(self._resume_btn)
        self._manage_tasks_btn = QPushButton("📋 管理全部任务")
        self._manage_tasks_btn.clicked.connect(self._on_manage_tasks)
        resume_layout.addWidget(self._manage_tasks_btn)
        self._dismiss_resume_btn = QPushButton("✖ 忽略")
        self._dismiss_resume_btn.clicked.connect(self._dismiss_resume)
        resume_layout.addWidget(self._dismiss_resume_btn)
        progress_layout.addWidget(self._resume_frame)

        layout.addWidget(progress_frame)

    def _build_tabs_and_log(self, layout: QVBoxLayout):
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, stretch=1)

        self._pdf_tab = PDFTab(self._get_cfg, self._start_worker_with_tracker, self._get_tracker, self._get_output_in_place)
        self._board_tab = BoardTab(self._get_cfg, self._start_worker_with_tracker, self._get_output_in_place)
        self._video_tab = VideoTab(self._get_cfg, self._start_worker_with_tracker, self._get_tracker, self._get_output_in_place)
        self._audio_tab = AudioTab(self._get_cfg, self._start_worker_with_tracker, self._get_output_in_place)
        self._social_tab = SocialTab(self._get_cfg, self._start_worker_with_tracker, self._get_tracker, self._get_output_in_place)

        self._tabs.addTab(self._pdf_tab, "📄 PDF 课本/课件")
        self._tabs.addTab(self._board_tab, "📷 板书/截图")
        self._tabs.addTab(self._video_tab, "🎬 录课视频")
        self._tabs.addTab(self._audio_tab, "🎙 语音识别")
        self._tabs.addTab(self._social_tab, "🌐 社交媒体视频")

        self._processor_tabs = {
            "pdf": self._pdf_tab,
            "board": self._board_tab,
            "video": self._video_tab,
            "audio": self._audio_tab,
            "social": self._social_tab,
        }

        self._build_log_window()

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("就绪 — 可直接拖放文件到输入框")

        # 收集所有标记为 qcr_run_button 的按钮到 _run_buttons
        for btn in self.findChildren(QPushButton):
            if btn.property("qcr_run_button"):
                self._run_buttons.append(btn)

    def _build_log_window(self):
        self._log_window = QWidget(self, Qt.Window)
        self._log_window.setWindowTitle("运行日志")
        self._log_window.resize(900, 520)
        log_layout = QVBoxLayout(self._log_window)
        log_layout.setContentsMargins(6, 6, 6, 6)
        self._log_text = QPlainTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setFont(MONO_FONT)
        self._log_text.setMaximumBlockCount(10000)
        log_layout.addWidget(self._log_text)

    # ---- API 设置 ----

    def _open_settings_dialog(self):
        from OCRLLM.gui.settings_dialog import SettingsDialog

        dlg = SettingsDialog(self, self._cfg)
        if dlg.exec_() == SettingsDialog.Accepted:
            self._cfg = dlg.apply_config()
            self._refresh_api_summary()
            self._api_status.setText("已应用设置")

    def _refresh_api_summary(self, *_args):
        if not hasattr(self, "_api_summary"):
            return
        s = self._settings
        key = s.value("ui/api_key", type=str) or ""
        google_enabled = s.value("ui/google_api_enabled", type=bool) if s.contains("ui/google_api_enabled") else False
        google_key = s.value("ui/google_api_key", type=str) or ""
        key_state = "Google Key 已填" if google_enabled and google_key else ("API Key 已填" if key else "API Key 未填")
        vis_enabled = s.value("ui/vision_api_enabled", type=bool) if s.contains("ui/vision_api_enabled") else False
        codex_enabled = s.value("ui/codex_vision_enabled", type=bool) if s.contains("ui/codex_vision_enabled") else False
        vis_provider = s.value("ui/vision_provider", type=str) or ""
        vis_info = f" | 视觉Provider: {vis_provider}" if vis_enabled else ""
        codex_info = " | Codex ask模式" if codex_enabled else ""
        google_info = " | 谷歌模式" if google_enabled else ""
        vision = (
            (migrate_stored_codex_vision_model(s.value("ui/codex_model", type=str)) if codex_enabled else "")
            or (s.value("ui/vision_model", type=str) if vis_enabled else "")
            or (s.value("ui/google_vision_model", type=str) if google_enabled else "")
            or s.value("ui/vision_model", type=str)
            or self._cfg.models.vision_model
            or "—"
        )
        audio = (
            (s.value("ui/google_audio_model", type=str) if google_enabled else "")
            or s.value("ui/audio_model", type=str)
            or self._cfg.models.asr_model
            or "—"
        )
        self._api_summary.setText(f"{key_state} | 视觉: {vision}{google_info}{codex_info}{vis_info} | 音频: {audio}")

    def _read_api_overrides_from_ui(self) -> tuple[dict, dict]:
        """从 QSettings 读取 API 设置并构建嵌套 updates 字典。

        SettingsDialog 负责将用户输入持久化到 QSettings；
        此处只从 QSettings 读取并构建 with_updates 所需的字典。
        """
        s = self._settings
        def _str(key, default=""):
            if not s.contains(key):
                return str(default or "").strip()
            return (s.value(key, type=str) or "").strip()
        def _bool(key, default=False):
            return s.value(key, type=bool) if s.contains(key) else bool(default)
        def _int(key, default=0):
            return int(s.value(key) if s.contains(key) else default)
        def _float(key, default=0.0):
            return float(s.value(key) if s.contains(key) else default)
        def _queue(key, default=None):
            if not s.contains(key):
                return list(default or [])
            try:
                import json
                return json.loads(s.value(key, type=str) or "[]")
            except Exception:
                return list(default or [])

        new_key = _str("ui/api_key", self._cfg.api.api_key)
        new_url = _str("ui/base_url", self._cfg.api.base_url)
        google_enabled = _bool("ui/google_api_enabled", self._cfg.google_api.enabled)
        google_key = _str("ui/google_api_key", self._cfg.google_api.api_key)
        google_vision_model = normalize_google_ocr_vision_model(
            _str("ui/google_vision_model") or self._cfg.google_api.vision_model
        )
        google_audio_model = _str("ui/google_audio_model") or self._cfg.google_api.audio_model
        google_parallel = _int("ui/google_parallel_requests", self._cfg.google_api.parallel_requests)
        google_stagger = _float("ui/google_request_stagger_seconds", self._cfg.google_api.request_stagger_seconds)
        google_vision_batch = _int("ui/google_vision_batch_size", self._cfg.google_api.vision_batch_size)
        google_video_batch = _int("ui/google_video_frame_batch_size", self._cfg.google_api.video_frame_batch_size)
        codex_enabled = _bool("ui/codex_vision_enabled", self._cfg.codex_vision.enabled)
        codex_command = _str("ui/codex_command", self._cfg.codex_vision.command) or "codex"
        codex_model = migrate_stored_codex_vision_model(_str("ui/codex_model", self._cfg.codex_vision.model))
        codex_reasoning = _str("ui/codex_reasoning_effort", self._cfg.codex_vision.reasoning_effort) or CODEX_VISION_DEFAULT_REASONING
        codex_timeout = _int("ui/codex_timeout_seconds", self._cfg.codex_vision.timeout_seconds)
        codex_parallel = max(1, _int("ui/codex_parallel_requests", self._cfg.codex_vision.parallel_requests))
        codex_stagger = max(0.0, _float("ui/codex_request_stagger_seconds", self._cfg.codex_vision.request_stagger_seconds))
        codex_vision_batch = max(1, _int("ui/codex_vision_batch_size", self._cfg.codex_vision.vision_batch_size))
        codex_video_batch = max(1, _int("ui/codex_video_frame_batch_size", self._cfg.codex_vision.video_frame_batch_size))
        vis_enabled = _bool("ui/vision_api_enabled", self._cfg.vision_api.enabled)
        vis_provider = _str("ui/vision_provider", self._cfg.vision_api.provider)
        vis_key = _str("ui/vision_api_key", self._cfg.vision_api.api_key)
        vis_url = _str("ui/vision_base_url", self._cfg.vision_api.base_url)
        vis_wire = (_str("ui/vision_wire_api", self._cfg.vision_api.wire_api) or "chat").lower()
        vis_reasoning = _str("ui/vision_reasoning_effort", self._cfg.vision_api.model_reasoning_effort)
        vis_network = _bool("ui/vision_network_access", self._cfg.vision_api.network_access)
        vis_no_store = _bool("ui/vision_disable_response_storage", self._cfg.vision_api.disable_response_storage)
        vision_model = codex_model if codex_enabled else (_str("ui/vision_model") or self._cfg.models.vision_model)
        audio_model = _str("ui/audio_model") or self._cfg.models.asr_model
        new_parallel = _int("ui/llm_parallel_requests", self._cfg.concurrency.llm_parallel_requests)
        new_stagger = _float("ui/llm_request_stagger_seconds", self._cfg.concurrency.llm_request_stagger_seconds)
        processing_batch = _int("ui/processing_batch_size", self._cfg.processing.batch_size)
        video_batch = _int("ui/video_batch_size", self._cfg.video.batch_size)
        paid_mode = _bool("ui/paid_mode", self._cfg.api.paid_mode)
        extra_keys_text = _str("ui/extra_api_keys")

        if s.contains("ui/extra_api_keys"):
            api_keys = [new_key] if new_key else []
            for k in extra_keys_text.split(","):
                k = k.strip()
                if k and k != new_key:
                    api_keys.append(k)
        else:
            api_keys = list(self._cfg.api.api_keys)
            if paid_mode and new_key and new_key not in api_keys:
                api_keys.insert(0, new_key)

        models_update: dict = {}
        if vision_model:
            models_update["vision_model"] = vision_model
            if not vis_enabled and not codex_enabled:
                models_update["text_model"] = vision_model
        if audio_model:
            models_update["asr_model"] = audio_model
            audio_meta = model_catalog.find_audio_model(audio_model)
            if audio_meta and audio_meta.kind == "asr_long":
                models_update["asr_short_model"] = "qwen3-asr-flash"
            else:
                models_update["asr_short_model"] = audio_model

        updates = {
            "api": {
                "api_key": new_key,
                "paid_mode": paid_mode,
                "api_keys": api_keys if paid_mode else [],
            },
            "google_api": {
                "enabled": google_enabled,
                "api_key": google_key,
                "vision_model": google_vision_model,
                "audio_model": google_audio_model,
                "text_model": google_vision_model or self._cfg.google_api.text_model,
                "parallel_requests": google_parallel,
                "request_stagger_seconds": google_stagger,
                "vision_batch_size": google_vision_batch,
                "video_frame_batch_size": google_video_batch,
                "api_keys": [google_key] if google_key else [],
            },
            "codex_vision": {
                "enabled": codex_enabled,
                "command": codex_command,
                "model": codex_model,
                "reasoning_effort": codex_reasoning,
                "timeout_seconds": codex_timeout,
                "parallel_requests": codex_parallel,
                "request_stagger_seconds": codex_stagger,
                "vision_batch_size": codex_vision_batch,
                "video_frame_batch_size": codex_video_batch,
            },
            "vision_api": {
                "enabled": vis_enabled,
                "provider": vis_provider,
                "api_key": vis_key,
                "base_url": vis_url,
                "wire_api": vis_wire,
                "model_reasoning_effort": vis_reasoning,
                "network_access": vis_network,
                "disable_response_storage": vis_no_store,
                "vision_model_queue": _queue("ui/vision_model_queue", self._cfg.vision_api.vision_model_queue),
            },
            "concurrency": {
                "llm_parallel_requests": codex_parallel if codex_enabled else (
                    new_parallel if new_parallel > 0 else self._cfg.concurrency.llm_parallel_requests
                ),
                "llm_request_stagger_seconds": codex_stagger if codex_enabled else new_stagger,
            },
            "processing": {
                "batch_size": codex_vision_batch if codex_enabled else processing_batch,
            },
            "video": {
                "batch_size": codex_video_batch if codex_enabled else video_batch,
            },
        }
        if new_url:
            updates["api"]["base_url"] = new_url
        if models_update:
            updates["models"] = models_update

        info = {
            "new_key": new_key, "new_url": new_url,
            "vision_model": vision_model, "audio_model": audio_model,
            "google_api_enabled": google_enabled,
            "google_api_key": google_key,
            "google_vision_model": google_vision_model,
            "google_audio_model": google_audio_model,
            "codex_enabled": codex_enabled,
            "codex_model": codex_model,
            "codex_reasoning_effort": codex_reasoning,
            "vision_api_enabled": vis_enabled,
            "vision_provider": vis_provider,
            "vision_api_key": vis_key,
            "vision_base_url": vis_url,
            "vision_wire_api": vis_wire,
            "auto_vision_model": False,
            "new_parallel": new_parallel, "new_stagger": new_stagger,
            "paid_mode": paid_mode, "api_keys": api_keys,
        }
        return updates, info

    def _connect_settings_autosave(self):
        self._output_in_place.toggled.connect(self._schedule_persist_ui_settings)

    def _schedule_persist_ui_settings(self, *_args):
        if self._restoring_ui_settings:
            return
        self._settings_save_timer.start(250)

    def _persist_ui_settings(self):
        self._settings.setValue("ui/output_in_place", self._output_in_place.isChecked())
        self._settings.sync()

    def _restore_ui_settings(self):
        self._restoring_ui_settings = True
        try:
            if self._settings.contains("ui/output_in_place"):
                self._output_in_place.setChecked(self._settings.value("ui/output_in_place", type=bool))
        finally:
            self._restoring_ui_settings = False

    # ---- Worker ----

    def _connect_worker(self):
        self._worker.progress.connect(self._on_progress)
        self._worker.content.connect(self._on_content)
        self._worker.finished_ok.connect(self._on_done)
        self._worker.finished_err.connect(self._on_error)
        self._worker.done.connect(self._on_worker_finished)
        self._worker.progress_detail.connect(self._on_progress_detail)

    def _sync_api_from_ui(self):
        """将 QSettings 中的 API 设置同步到 config。"""
        updates, _info = self._read_api_overrides_from_ui()
        self._cfg = self._cfg.with_updates(**updates)

    def _start_worker_with_tracker(self, task_func):
        """启动带进度追踪器的 worker。"""
        if self._worker.is_running:
            QMessageBox.warning(self, "提示", "有任务正在运行，请等待完成")
            return False

        # 启动前自动同步 GUI 输入框的 API 设置到 config
        self._sync_api_from_ui()
        if self._cfg.google_api.enabled and not self._cfg.google_api.api_key:
            QMessageBox.warning(self, "提示", "谷歌模式已启用，但 Google API Key 为空")
            return False
        if not self._cfg.google_api.enabled and not self._cfg.api.api_key and not self._cfg.codex_vision.enabled and not (
            self._cfg.vision_api.enabled and self._cfg.vision_api.api_key
        ):
            QMessageBox.warning(self, "提示", "API Key 不能为空，请在 API 设置中填入 Key 或视觉 Provider Key")
            return False
        if self._cfg.vision_api.enabled and not self._cfg.codex_vision.enabled and (
            not self._cfg.vision_api.api_key or not self._cfg.vision_api.base_url
        ):
            QMessageBox.warning(self, "提示", "视觉独立 Provider 已启用，但视觉 API Key 或 Base URL 为空")
            return False

        self._log_text.clear()
        self._log_buffer.clear()
        self._log_flush_timer.stop()
        self._show_log_window()
        self._free_tier_warned.clear()
        self._status.showMessage("处理中...")
        self._progress_bar.setValue(0)
        self._progress_label.setText("正在启动...")
        self._tracker = ProgressTracker()
        for btn in self._run_buttons:
            btn.setEnabled(False)
        self._worker.start(task_func, tracker=self._tracker)
        return True

    def _vision_provider_model_warning(self) -> str:
        model = (self._cfg.models.vision_model or "").strip()
        if not self._looks_like_qwen_model(model):
            return ""
        if self._cfg.vision_api.enabled:
            provider = self._cfg.vision_api.provider
            base_url = self._cfg.vision_api.base_url
        else:
            provider = ""
            base_url = self._cfg.api.base_url
        if not self._looks_like_external_openai_provider(provider, base_url):
            return ""
        return (
            f"当前视觉模型仍是 {model}，但视觉 Provider/Base URL 看起来不是 DashScope。\n\n"
            "请点击“更换视觉模型...”并选择或测试添加该 Provider 支持的模型 ID，"
            "再开始图片/PDF/视频帧识别。"
        )

    @staticmethod
    def _looks_like_qwen_model(model: str) -> bool:
        lowered = model.lower()
        return lowered.startswith("qwen") or lowered.startswith("qwq")

    @staticmethod
    def _looks_like_external_openai_provider(provider: str, base_url: str) -> bool:
        marker = f"{provider} {base_url}".lower()
        if not marker.strip():
            return False
        if "dashscope" in marker or "aliyuncs" in marker:
            return False
        return bool(base_url.strip())

    def _show_log_window(self):
        if self._log_window is None:
            return
        self._log_window.show()
        self._log_window.raise_()
        self._log_window.activateWindow()

    @pyqtSlot(int, int, str)
    def _on_progress(self, current, total, msg):
        self._status.showMessage(f"[{current}/{total}] {msg}")
        self._progress_label.setText(msg)
        tracker_task = self._tracker.get_snapshot().get("task_type") if self._tracker else ""
        if total > 0 and tracker_task not in {"pdf", "video"}:
            pct = int(current / total * 100)
            self._progress_bar.setValue(pct)

    @pyqtSlot(str, float, dict)
    def _on_progress_detail(self, message, percent, snapshot):
        """接收定时轮询的人类友好进度。"""
        self._progress_label.setText(message)
        if percent > 0:
            self._progress_bar.setValue(int(min(percent, 100)))

    @pyqtSlot(str, str)
    def _on_content(self, text, label):
        self._flush_log_buffer()
        header = f"\n{'─' * 40}\n📝 {label}\n{'─' * 40}\n" if label else "\n"
        display = text if len(text) <= 2000 else text[:2000] + f"\n... (共 {len(text)} 字符，已截断)\n"
        self._log_text.appendPlainText(header + display)

    @pyqtSlot(str)
    def _append_log(self, msg):
        self._log_buffer.append(msg)
        if not self._log_flush_timer.isActive():
            self._log_flush_timer.start(50)

    def _flush_log_buffer(self):
        if not self._log_buffer:
            return
        self._log_text.appendPlainText("\n".join(self._log_buffer))
        self._log_buffer.clear()

    @pyqtSlot(str)
    def _on_done(self, msg):
        self._flush_log_buffer()
        logging.info(msg)
        self._status.showMessage("✅ 完成")
        self._progress_bar.setValue(100)
        self._progress_label.setText("✅ 任务完成")
        if self._suppress_worker_dialogs:
            return
        QMessageBox.information(self, "完成", msg)

    @pyqtSlot(str)
    def _on_error(self, msg):
        self._flush_log_buffer()
        logging.error("任务失败: %s", msg)
        cancelled = msg.strip() == "任务已取消"
        self._status.showMessage("已取消" if cancelled else "❌ 出错")
        self._progress_label.setText("已取消" if cancelled else "❌ 任务出错")
        if self._suppress_worker_dialogs:
            return
        QMessageBox.critical(self, "错误", msg)

    @pyqtSlot()
    def _on_worker_finished(self):
        self._flush_log_buffer()
        if self._close_after_worker:
            self._allow_immediate_close = True
            self.close()
            return
        for btn in self._run_buttons:
            btn.setEnabled(True)
        self._suppress_worker_dialogs = False
        # 完成后再次检查是否有待续传任务
        self._check_resume_on_startup()

    # ---- 断点续传 ----

    def _check_resume_on_startup(self):
        """启动时检查是否有未完成的任务。"""
        try:
            mgr = CheckpointManager(self._cfg.paths.output_dir)
            incomplete = mgr.list_incomplete()
            if not incomplete:
                self._resume_frame.setVisible(False)
                self._pending_resume = None
                return

            # 优先选择之前正在查看的任务
            preferred_key = self._pending_resume.resume_key if self._pending_resume is not None else None
            cp = mgr.select_incomplete(preferred_key=preferred_key)
            if cp is not None:
                self._pending_resume = cp
                task_desc = (
                    "PDF" if cp.task_type == "pdf"
                    else "视频" if cp.task_type == "video"
                    else "音频" if cp.task_type == "audio"
                    else cp.task_type
                )
                src_name = Path(cp.source_path).name
                count = len(incomplete)
                if count == 1:
                    self._resume_label.setText(
                        f"发现未完成的{task_desc}任务: {src_name} ({cp.progress_text})"
                    )
                    self._manage_tasks_btn.setVisible(False)
                else:
                    self._resume_label.setText(
                        f"发现 {count} 个未完成任务 | 最近: {src_name} ({cp.progress_text})"
                    )
                    self._manage_tasks_btn.setVisible(True)
                self._resume_frame.setVisible(True)
            else:
                self._resume_frame.setVisible(False)
                self._pending_resume = None
        except Exception:
            self._resume_frame.setVisible(False)
            self._pending_resume = None

    def _on_resume_clicked(self):
        """用户点击继续任务。"""
        cp = self._pending_resume
        if not cp:
            return
        self._resume_frame.setVisible(False)

        if cp.task_type == "pdf":
            self._resume_pdf(cp)
        elif cp.task_type == "video":
            self._resume_video(cp)
        elif cp.task_type == "audio":
            self._resume_audio(cp)

    def _dismiss_resume(self):
        """忽略断点续传提示（不删除检查点）。"""
        self._resume_frame.setVisible(False)
        self._pending_resume = None

    def _on_manage_tasks(self):
        """打开任务管理对话框，浏览/继续/删除未完成任务。"""
        mgr = CheckpointManager(self._cfg.paths.output_dir)
        dlg = IncompleteTasksDialog(mgr, parent=self)
        if dlg.exec_() == IncompleteTasksDialog.Accepted:
            checkpoints = getattr(dlg, "selected_checkpoints", [])
            if checkpoints and dlg.action == "resume":
                self._resume_many(checkpoints)
                return
        # 刷新横幅（可能有任务被删除了）
        self._check_resume_on_startup()

    def _resume_many(self, checkpoints):
        checkpoints = list(checkpoints)
        if not checkpoints:
            return
        if len(checkpoints) == 1:
            self._pending_resume = checkpoints[0]
            self._on_resume_clicked()
            return

        def task(reporter):
            results = []
            total = len(checkpoints)
            for idx, cp in enumerate(checkpoints, start=1):
                name = Path(cp.source_path).name
                reporter.progress(idx - 1, total, f"继续未完成任务 {idx}/{total}: {name}")
                results.append(self._run_resume_checkpoint(cp, reporter))
                reporter.progress(idx, total, f"已完成续传 {idx}/{total}: {name}")
            return "批量续传完成:\n" + "\n".join(f"- {item}" for item in results)

        self._resume_frame.setVisible(False)
        self._start_worker_with_tracker(task)

    def _resume_pdf(self, cp):
        """恢复 PDF 任务。"""
        def task(reporter):
            return self._run_resume_checkpoint(cp, reporter)

        self._start_worker_with_tracker(task)

    def _resume_video(self, cp):
        """恢复视频任务。"""
        def task(reporter):
            return self._run_resume_checkpoint(cp, reporter)

        self._start_worker_with_tracker(task)

    def _resume_audio(self, cp):
        """恢复音频任务。"""
        def task(reporter):
            return self._run_resume_checkpoint(cp, reporter)

        self._start_worker_with_tracker(task)

    def _run_resume_checkpoint(self, cp, reporter) -> str:
        if cp.task_type == "pdf":
            from OCRLLM.processors.pdf import PDFProcessor
            cfg = self._get_cfg()
            proc = PDFProcessor(cfg=cfg, reporter=reporter, tracker=self._tracker)
            result = proc.process(**PDFProcessor.resume_options_from_checkpoint(cp))
            return f"PDF 续传完成: {result}"
        if cp.task_type == "video":
            from OCRLLM.processors.video import VideoProcessor
            cfg = self._get_cfg()
            proc = VideoProcessor(cfg=cfg, reporter=reporter, tracker=self._tracker)
            result = proc.process(**VideoProcessor.resume_options_from_checkpoint(cp))
            return f"视频续传完成: {result.get('output_dir', '')}"
        if cp.task_type == "audio":
            from OCRLLM.processors.audio import AudioProcessor
            cfg = self._get_cfg()
            proc = AudioProcessor(cfg=cfg, reporter=reporter, tracker=self._tracker)
            result = proc.process(**AudioProcessor.resume_options_from_checkpoint(cp))
            return f"音频续传完成: {result}"
        raise ValueError(f"不支持续传的任务类型: {cp.task_type}")

    # ---- Misc ----

    def _spawn_windows(self):
        count = self._spawn_spin.value()
        # 与 main.py 保持一致，统一使用 -m 模块执行方式
        project_root = str(Path(__file__).resolve().parent.parent.parent)
        for offset in range(1, count + 1):
            child_index = self._window_index + offset
            kw = {}
            if sys.platform == "win32":
                # 完全分离子进程：不继承句柄，不共享控制台，
                # 防止子进程干扰父进程的网络连接和文件锁。
                kw["creationflags"] = (
                    subprocess.DETACHED_PROCESS
                    | subprocess.CREATE_NEW_PROCESS_GROUP
                )
                kw["close_fds"] = True
            subprocess.Popen(
                [sys.executable, "-m", "OCRLLM.main", "--child-index", str(child_index)],
                cwd=project_root, **kw)

    def dragEnterEvent(self, event):
        """拖放进入事件：验证文件类型是否受支持。"""
        urls = event.mimeData().urls()
        local_paths = [url.toLocalFile() for url in urls if url.toLocalFile()]
        if not local_paths:
            event.ignore()
            return
        try:
            route_input_paths(local_paths, allow_multiple_same_type=True)
        except (InputRoutingError, KeyError):
            event.ignore()
            return
        event.acceptProposedAction()

    def dropEvent(self, event):
        """拖放释放事件：路由文件到对应的处理 Tab。"""
        urls = event.mimeData().urls()
        paths = [url.toLocalFile() for url in urls if url.toLocalFile()]
        if not paths:
            event.ignore()
            return
        self._route_inputs_to_tab(paths)
        event.acceptProposedAction()

    def _route_inputs_to_tab(self, paths: list[str]):
        try:
            routed = route_input_paths(paths, allow_multiple_same_type=True)
        except KeyError as exc:
            QMessageBox.warning(self, "无法识别", f"不支持的文件类型: {exc}")
            return
        except InputRoutingError as exc:
            QMessageBox.warning(self, "无法识别", str(exc))
            return

        spec = routed.spec
        tab = self._processor_tabs.get(spec.key)
        if tab is None:
            QMessageBox.information(
                self,
                "已识别文件类型",
                f"已识别为 {spec.display_name}，但 GUI 工作流尚未接入。\n"
                f"当前该处理器仅创建了占位骨架。",
            )
            self._status.showMessage(f"已识别文件类型: {spec.display_name}（尚未接入 GUI）")
            return

        tab.set_input_paths(list(routed.paths))
        self._tabs.setCurrentWidget(tab)
        self._status.showMessage(
            f"已识别为 {spec.display_name}: {', '.join(Path(p).name for p in routed.paths[:3])}"
        )

    def closeEvent(self, event):
        """窗口关闭事件：若有任务运行中则弹窗确认。"""
        if self._allow_immediate_close:
            self._cleanup_log_handler()
            self._persist_ui_settings()
            event.accept()
            return
        if self._worker.is_running:
            reply = QMessageBox.question(
                self, "确认关闭",
                "有任务正在运行，关闭窗口将中断任务。确定关闭？\n"
                "（已完成的部分会被保存，下次启动可继续）",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                event.ignore()
                return
            self._close_after_worker = True
            self._suppress_worker_dialogs = True
            self._status.showMessage("正在取消任务并关闭...")
            self._progress_label.setText("正在取消任务并关闭...")
            self._worker.request_cancel()
            if not self._worker.is_running:
                self._allow_immediate_close = True
                self._cleanup_log_handler()
                event.accept()
                return
            # H3: 15s 超时强制关闭，防止 worker 不响应取消时窗口永远无法关闭
            self._close_timeout_timer = QTimer(self)
            self._close_timeout_timer.setSingleShot(True)
            self._close_timeout_timer.timeout.connect(self._force_close)
            self._close_timeout_timer.start(15000)
            event.ignore()
            return
        self._cleanup_log_handler()
        self._persist_ui_settings()
        event.accept()

    def _force_close(self):
        """H3: 超时后强制关闭窗口，防止 worker 不响应取消时窗口永远无法关闭。"""
        logger.warning("[GUI] Worker 未在 15s 内结束，强制关闭窗口")
        self._allow_immediate_close = True
        self.close()

    def deleteLater(self):
        self._cleanup_log_handler()
        super().deleteLater()

    def _cleanup_log_handler(self):
        """M9: 关闭窗口时移除日志 handler，防止多次 open/close 后 handler 累积。"""
        if self._qt_log_handler is not None:
            logging.getLogger().removeHandler(self._qt_log_handler)
            self._qt_log_handler = None

    def _dispatch_free_tier_signal(self, old_model: str, new_model: str, kind: str):
        """LLMClient 后台线程通过 set_free_tier_notifier 注册到这里；
        转成 Qt 信号让 GUI 线程弹窗。"""
        try:
            self._free_tier_signal.emit(old_model, new_model, kind)
        except RuntimeError:
            pass

    @pyqtSlot(str, str, str)
    def _on_free_tier_switch(self, old_model: str, new_model: str, kind: str):
        key = (old_model, new_model)
        if key in self._free_tier_warned:
            return
        self._free_tier_warned.add(key)
        msg = (f"模型 '{old_model}' 的免费额度已耗尽，"
               f"已自动切换到 '{new_model}' 继续 ({kind})。\n\n"
               "如需阻止自动切换，可去阿里云百炼控制台开通付费，"
               "或在'更换模型'里挑一个仍有额度的模型。")
        QMessageBox.warning(self, "免费额度耗尽 → 自动切换", msg)
        logging.warning("[FREE_TIER] 已弹窗告知: %s -> %s (%s)", old_model, new_model, kind)

    def _init_logging(self):
        setup_logging(logging.DEBUG)
        handler = _QtLogHandler(self._log_signal)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
        # 避免同进程多窗口时重复追加 handler
        root = logging.getLogger()
        if not any(isinstance(h, _QtLogHandler) for h in root.handlers):
            root.addHandler(handler)
        self._qt_log_handler = handler
        self._log_signal.connect(self._append_log)


# ---- 公共辅助函数（供 Tab 使用） ----

def make_action_buttons(
    run_text: str,
    run_cb: Callable,
    reset_cb: Callable,
    extra: list[tuple[str, Callable]] = None,
    extra_widgets: list[QWidget] = None,
    run_button_list: list[QPushButton] = None,
) -> QHBoxLayout:
    """创建带「运行」和「重置提示词」按钮的水平布局。

    Args:
        run_text: 运行按钮文本。
        run_cb: 运行按钮回调。
        reset_cb: 重置按钮回调。
        extra: 额外按钮列表 ``[(text, callback), ...]``。
        extra_widgets: 已创建好的额外控件，会放在运行按钮之后。
        run_button_list: 可选的列表，运行按钮会被追加到其中，用于统一管理禁用/启用。

    Returns:
        QHBoxLayout 布局。
    """
    btns = QHBoxLayout()
    b_run = QPushButton(run_text)
    b_run.setProperty("qcr_run_button", True)
    b_run.clicked.connect(run_cb)
    btns.addWidget(b_run)
    if run_button_list is not None:
        run_button_list.append(b_run)
    if extra_widgets:
        for widget in extra_widgets:
            btns.addWidget(widget)
    if extra:
        for text, cb in extra:
            b = QPushButton(text)
            b.clicked.connect(cb)
            btns.addWidget(b)
    b_reset = QPushButton("重置提示词")
    b_reset.clicked.connect(reset_cb)
    btns.addWidget(b_reset)
    btns.addStretch()
    return btns
