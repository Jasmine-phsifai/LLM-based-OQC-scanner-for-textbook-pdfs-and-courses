"""
API / 模型设置独立弹窗 — 替代原主窗口内嵌的可展开设置面板。

包含:
  · DashScope API Key / Base URL
  · 视觉独立 Provider（OpenAI 兼容）+ 扫描模型
  · 视觉模型 / 音频模型选择
  · LLM 并发 / 错峰参数
  · 付费模式 / API 池
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox,
    QPushButton, QScrollArea, QSpinBox, QVBoxLayout,
    QWidget, QFrame, QAbstractItemView,
)
from PyQt5.QtCore import QSettings, Qt, QTimer

# Shared pool for background model-list fetches so a slow /models call or a
# stalled google.com probe never blocks the settings window's event loop.
_FETCH_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ocrllm-model-fetch")

from OCRLLM.config import AppConfig, normalize_google_ocr_vision_model
from OCRLLM.core import model_catalog

try:
    from OCRLLM.core.codex_vision import (
        CODEX_VISION_DEFAULT_MODEL,
        CODEX_VISION_DEFAULT_REASONING,
        CODEX_VISION_MODEL_CHOICES,
        CODEX_VISION_REASONING_LEVELS,
        inspect_codex_cli,
        migrate_stored_codex_vision_model,
        normalize_codex_vision_model,
    )
    _HAS_CODEX = True
except ImportError:
    CODEX_VISION_DEFAULT_MODEL = "codex"
    CODEX_VISION_DEFAULT_REASONING = ""
    CODEX_VISION_MODEL_CHOICES = ["codex"]
    CODEX_VISION_REASONING_LEVELS = ["", "low", "medium", "high"]
    def migrate_stored_codex_vision_model(model: str | None) -> str:
        return normalize_codex_vision_model(model)

    def normalize_codex_vision_model(model: str | None) -> str:
        return (model or CODEX_VISION_DEFAULT_MODEL).strip()
    _HAS_CODEX = False

    def inspect_codex_cli(cfg):  # type: ignore[no-redef]
        from dataclasses import dataclass
        @dataclass
        class _R:
            ok: bool = False
            message: str = "codex_vision 模块未安装"
        return _R()

SETTINGS_ORG = "OCRLLM"
SETTINGS_APP = "QCR"
logger = logging.getLogger(__name__)


def _scan_models_from_api(base_url: str, api_key: str) -> list[str]:
    """从 OpenAI 兼容 API 的 /models 端点扫描可用模型列表。

    Args:
        base_url: API base URL（如 https://ai-api.mozheyu.fun/v1）
        api_key: API key

    Returns:
        模型 ID 列表；失败时返回空列表。
    """
    url = base_url.rstrip("/") + "/models"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        body = json.loads(resp.read().decode())
        if isinstance(body, dict) and "data" in body:
            models = [m.get("id", "") for m in body["data"] if m.get("id")]
        elif isinstance(body, dict) and "models" in body:
            models = [m.get("name", "") for m in body["models"] if m.get("name")]
        else:
            models = []
        return sorted(models)
    except Exception as e:
        logger.warning("扫描模型失败 (%s): %s", url, e)
        return []


class SettingsDialog(QDialog):
    """API / 模型设置弹窗。读取 QSettings 和当前 AppConfig，确认后回写。"""

    def __init__(self, parent: QWidget, cfg: AppConfig):
        super().__init__(parent)
        self._cfg = cfg
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self._restoring_settings = False
        self._active_fetch_timers: list[QTimer] = []

        self._pending_vision_model: str = cfg.models.vision_model
        self._pending_audio_model: str = cfg.models.asr_model
        self._pending_google_vision_model: str = cfg.google_api.vision_model
        self._pending_google_audio_model: str = cfg.google_api.audio_model
        self._scanned_models: list[str] = []
        self._previous_non_codex_vision_model: str = ""

        self._init_ui()
        self._restore_from_settings()

    # ---- public ----

    def apply_config(self) -> AppConfig:
        """返回更新后的 AppConfig（不修改原实例）。"""
        updates, _info = self._read_overrides()
        return self._cfg.with_updates(**updates)

    # ---- UI ----

    def _init_ui(self):
        self.setWindowTitle("API / 模型设置")
        self.setMinimumSize(840, 640)
        self.resize(920, 760)
        self.setSizeGripEnabled(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)

        # ---- DashScope ----
        dash_group = QGroupBox("DashScope 主 API")
        self._dash_group = dash_group
        dash_layout = QVBoxLayout(dash_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("API Key:"))
        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.Password)
        row1.addWidget(self._api_key_input, stretch=1)
        self._api_key_toggle = QPushButton("显示")
        self._api_key_toggle.setFixedWidth(50)
        self._api_key_toggle.setCheckable(True)
        self._api_key_toggle.toggled.connect(
            lambda c: self._api_key_input.setEchoMode(
                QLineEdit.Normal if c else QLineEdit.Password))
        row1.addWidget(self._api_key_toggle)
        dash_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Base URL:"))
        self._base_url_input = QLineEdit()
        self._base_url_input.setPlaceholderText("https://dashscope.aliyuncs.com/compatible-mode/v1")
        row2.addWidget(self._base_url_input, stretch=1)
        self._refresh_dashscope_models_btn = QPushButton("刷新百炼模型")
        self._refresh_dashscope_models_btn.setToolTip("调用百炼 OpenAI 兼容 /models 获取当前账号真实可用模型")
        self._refresh_dashscope_models_btn.clicked.connect(lambda: self._refresh_bailian_models(force=True, notify=True))
        row2.addWidget(self._refresh_dashscope_models_btn)
        dash_layout.addLayout(row2)

        # 视觉/音频模型选择（生效模型；被 Codex 或独立视觉 Provider 接管时改由那边写回同一字段）
        vis_model_row = QHBoxLayout()
        vis_model_row.addWidget(QLabel("主视觉模型:"))
        self._vision_model_combo = QComboBox()
        self._vision_model_combo.setEditable(True)
        self._vision_model_combo.setMinimumWidth(280)
        self._vision_model_combo.setToolTip("主模型 ID；可直接输入或从扫描列表/内置清单选择")
        self._vision_model_combo.currentTextChanged.connect(self._on_vision_model_text_changed)
        vis_model_row.addWidget(self._vision_model_combo, stretch=1)
        self._btn_pick_vision = QPushButton("选择模型...")
        self._btn_pick_vision.clicked.connect(self._open_vision_picker)
        vis_model_row.addWidget(self._btn_pick_vision)
        dash_layout.addLayout(vis_model_row)

        vision_shared_hint = QLabel(
            "此字段是最终生效的视觉模型；启用「本机 Codex 识图」或「独立视觉 Provider」时，"
            "会由那边的模型选择改写这里，而不是各自维护一份。"
        )
        vision_shared_hint.setWordWrap(True)
        dash_layout.addWidget(vision_shared_hint)

        # 模型降级队列
        queue_group = QGroupBox("模型降级队列（主模型额度耗尽时自动按顺序切换）")
        queue_outer = QVBoxLayout(queue_group)

        self._model_queue_list = QListWidget()
        self._model_queue_list.setAlternatingRowColors(True)
        self._model_queue_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._model_queue_list.setToolTip("优先级从上到下递减；主模型耗尽后依次尝试队列中的模型。\n留空则不启用降级切换。")
        self._model_queue_list.setMaximumHeight(140)
        queue_outer.addWidget(self._model_queue_list)

        queue_btn_row = QHBoxLayout()
        btn_add_scanned = QPushButton("添加扫描模型")
        btn_add_scanned.setToolTip("从扫描结果下拉框中选择模型添加到队列")
        btn_add_scanned.clicked.connect(self._on_queue_add_scanned)
        queue_btn_row.addWidget(btn_add_scanned)
        btn_add_all = QPushButton("全选扫描模型")
        btn_add_all.setToolTip("将所有扫描到的模型全部加入降级队列（免费 API 适用）")
        btn_add_all.clicked.connect(self._on_queue_select_all)
        queue_btn_row.addWidget(btn_add_all)
        btn_remove = QPushButton("移除选中")
        btn_remove.clicked.connect(self._on_queue_remove)
        queue_btn_row.addWidget(btn_remove)
        btn_up = QPushButton("↑ 上移")
        btn_up.clicked.connect(self._on_queue_move_up)
        queue_btn_row.addWidget(btn_up)
        btn_down = QPushButton("↓ 下移")
        btn_down.clicked.connect(self._on_queue_move_down)
        queue_btn_row.addWidget(btn_down)
        queue_btn_row.addStretch()
        queue_outer.addLayout(queue_btn_row)
        dash_layout.addWidget(queue_group)

        # 音频模型（仅 DashScope 长录音识别使用）
        audio_model_row = QHBoxLayout()
        audio_model_row.addWidget(QLabel("音频模型:"))
        self._audio_model_label = QLabel()
        self._audio_model_label.setStyleSheet("font-weight: bold; padding: 2px 8px;")
        audio_model_row.addWidget(self._audio_model_label, stretch=1)
        btn_pick_audio = QPushButton("选择模型...")
        btn_pick_audio.clicked.connect(self._open_audio_picker)
        audio_model_row.addWidget(btn_pick_audio)
        dash_layout.addLayout(audio_model_row)

        self._refresh_model_labels()

        body_layout.addWidget(dash_group)

        # ---- Google Gemini ----
        google_group = QGroupBox("谷歌模式（Google AI Studio / Gemini SDK）")
        self._google_group = google_group
        google_layout = QVBoxLayout(google_group)

        google_toggle_row = QHBoxLayout()
        self._google_enabled_cb = QCheckBox("启用谷歌 Gemini（长音频走 Google；视觉可由 Codex/独立 Provider 接管）")
        self._google_enabled_cb.toggled.connect(self._on_google_enabled_changed)
        google_toggle_row.addWidget(self._google_enabled_cb)
        google_toggle_row.addStretch()
        self._refresh_google_models_btn = QPushButton("测试网络并拉取模型")
        self._refresh_google_models_btn.setToolTip("先访问 google.com，再用 Google Models API 实时拉取当前账号可用模型")
        self._refresh_google_models_btn.clicked.connect(lambda: self._refresh_google_models(force=True, notify=True))
        google_toggle_row.addWidget(self._refresh_google_models_btn)
        google_layout.addLayout(google_toggle_row)

        google_key_row = QHBoxLayout()
        google_key_row.addWidget(QLabel("Google API Key:"))
        self._google_key_input = QLineEdit()
        self._google_key_input.setEchoMode(QLineEdit.Password)
        self._google_key_input.setPlaceholderText("Google AI Studio / Gemini API Key")
        google_key_row.addWidget(self._google_key_input, stretch=1)
        self._google_key_toggle = QPushButton("显示")
        self._google_key_toggle.setFixedWidth(50)
        self._google_key_toggle.setCheckable(True)
        self._google_key_toggle.toggled.connect(
            lambda c: self._google_key_input.setEchoMode(QLineEdit.Normal if c else QLineEdit.Password))
        google_key_row.addWidget(self._google_key_toggle)
        google_layout.addLayout(google_key_row)

        google_model_row = QHBoxLayout()
        google_model_row.addWidget(QLabel("图片/视频帧模型:"))
        self._google_vision_model_combo = QComboBox()
        self._google_vision_model_combo.setEditable(True)
        self._google_vision_model_combo.currentTextChanged.connect(
            lambda text: setattr(self, "_pending_google_vision_model", text.strip()))
        google_model_row.addWidget(self._google_vision_model_combo, stretch=1)
        google_model_row.addWidget(QLabel("长音频模型:"))
        self._google_audio_model_combo = QComboBox()
        self._google_audio_model_combo.setEditable(True)
        self._google_audio_model_combo.currentTextChanged.connect(
            lambda text: setattr(self, "_pending_google_audio_model", text.strip()))
        google_model_row.addWidget(self._google_audio_model_combo, stretch=1)
        google_layout.addLayout(google_model_row)

        google_perf_row = QHBoxLayout()
        google_perf_row.addWidget(QLabel("Google 并行线程:"))
        self._google_parallel_input = QSpinBox()
        self._google_parallel_input.setRange(1, 256)
        self._google_parallel_input.setToolTip("Google 模式独立并发；实际上限仍受 Google 项目级限流影响")
        google_perf_row.addWidget(self._google_parallel_input)
        google_perf_row.addWidget(QLabel("Google 错峰间隔(秒):"))
        self._google_stagger_input = QDoubleSpinBox()
        self._google_stagger_input.setRange(0.0, 3600.0)
        self._google_stagger_input.setDecimals(1)
        self._google_stagger_input.setSingleStep(0.5)
        google_perf_row.addWidget(self._google_stagger_input)
        google_perf_row.addWidget(QLabel("图片批大小:"))
        self._google_vision_batch_input = QSpinBox()
        self._google_vision_batch_input.setRange(1, 200)
        google_perf_row.addWidget(self._google_vision_batch_input)
        google_perf_row.addWidget(QLabel("视频帧批大小:"))
        self._google_video_batch_input = QSpinBox()
        self._google_video_batch_input.setRange(1, 200)
        google_perf_row.addWidget(self._google_video_batch_input)
        google_layout.addLayout(google_perf_row)

        google_hint = QLabel(
            "说明：Google Gemini 使用官方 google-genai SDK 和 Files API；长音频优先走 Google。"
            "图片和视频帧按优先级选择 Codex、OpenAI-compatible 视觉 Provider、Google。"
        )
        google_hint.setWordWrap(True)
        google_layout.addWidget(google_hint)

        self._populate_google_model_combos()
        body_layout.addWidget(google_group)

        # ---- 本机 Codex 识图 ----
        codex_group = QGroupBox("本机 Codex 识图（ask 模式）")
        codex_layout = QVBoxLayout(codex_group)

        codex_toggle_row = QHBoxLayout()
        self._codex_enabled_cb = QCheckBox("启用本机 Codex 进行图片识别")
        self._codex_enabled_cb.setToolTip("启用后图片/视频帧识别走本机 codex exec；Google 长音频和 Provider 配置保留。")
        self._codex_enabled_cb.toggled.connect(self._on_codex_enabled_changed)
        codex_toggle_row.addWidget(self._codex_enabled_cb)
        codex_toggle_row.addStretch()
        self._codex_check_btn = QPushButton("检测 Codex")
        self._codex_check_btn.clicked.connect(self._on_codex_check_clicked)
        codex_toggle_row.addWidget(self._codex_check_btn)
        codex_layout.addLayout(codex_toggle_row)

        codex_row = QHBoxLayout()
        codex_row.addWidget(QLabel("模型:"))
        self._codex_model_combo = QComboBox()
        self._codex_model_combo.setEditable(True)
        self._codex_model_combo.addItems(CODEX_VISION_MODEL_CHOICES)
        self._codex_model_combo.setCurrentText(CODEX_VISION_DEFAULT_MODEL)
        self._codex_model_combo.currentTextChanged.connect(self._on_codex_model_changed)
        codex_row.addWidget(self._codex_model_combo, stretch=1)
        codex_row.addWidget(QLabel("思考强度:"))
        self._codex_reasoning_combo = QComboBox()
        self._codex_reasoning_combo.addItems(CODEX_VISION_REASONING_LEVELS)
        self._codex_reasoning_combo.setCurrentText(CODEX_VISION_DEFAULT_REASONING)
        codex_row.addWidget(self._codex_reasoning_combo)
        codex_layout.addLayout(codex_row)

        codex_row2 = QHBoxLayout()
        codex_row2.addWidget(QLabel("命令:"))
        self._codex_command_input = QLineEdit("codex")
        codex_row2.addWidget(self._codex_command_input, stretch=1)
        codex_row2.addWidget(QLabel("超时(秒):"))
        self._codex_timeout_input = QSpinBox()
        self._codex_timeout_input.setRange(30, 7200)
        self._codex_timeout_input.setValue(1800)
        codex_row2.addWidget(self._codex_timeout_input)
        codex_layout.addLayout(codex_row2)

        codex_perf_row = QHBoxLayout()
        codex_perf_row.addWidget(QLabel("Codex 并行数量:"))
        self._codex_parallel_input = QSpinBox()
        self._codex_parallel_input.setRange(1, 256)
        self._codex_parallel_input.setToolTip("本机 Codex 模式独立并发；会映射到旧处理器的 LLM 并发数")
        codex_perf_row.addWidget(self._codex_parallel_input)
        codex_perf_row.addWidget(QLabel("Codex 间隔(秒):"))
        self._codex_stagger_input = QDoubleSpinBox()
        self._codex_stagger_input.setRange(0.0, 3600.0)
        self._codex_stagger_input.setDecimals(1)
        self._codex_stagger_input.setSingleStep(0.5)
        codex_perf_row.addWidget(self._codex_stagger_input)
        codex_perf_row.addWidget(QLabel("图片数量:"))
        self._codex_vision_batch_input = QSpinBox()
        self._codex_vision_batch_input.setRange(1, 200)
        self._codex_vision_batch_input.setToolTip("PDF/板书每批传给 Codex 的图片数量")
        codex_perf_row.addWidget(self._codex_vision_batch_input)
        codex_perf_row.addWidget(QLabel("视频帧数量:"))
        self._codex_video_batch_input = QSpinBox()
        self._codex_video_batch_input.setRange(1, 200)
        self._codex_video_batch_input.setToolTip("录课视频板书识别每批传给 Codex 的帧数量")
        codex_perf_row.addWidget(self._codex_video_batch_input)
        codex_layout.addLayout(codex_perf_row)

        codex_hint = QLabel("说明：Codex 模式只接管图片/视频帧识别；长音频仍可走 Google，Provider 设置会保留。")
        codex_hint.setWordWrap(True)
        codex_layout.addWidget(codex_hint)
        body_layout.addWidget(codex_group)

        # ---- 视觉 Provider ----
        vis_group = QGroupBox("视觉模型独立 Provider（OpenAI 兼容）")
        vis_layout = QVBoxLayout(vis_group)

        vis_toggle_row = QHBoxLayout()
        self._vision_enabled_cb = QCheckBox("启用独立视觉 Provider")
        self._vision_enabled_cb.toggled.connect(self._on_vision_enabled_changed)
        vis_toggle_row.addWidget(self._vision_enabled_cb)
        vis_toggle_row.addStretch()
        vis_layout.addLayout(vis_toggle_row)

        vis_row1 = QHBoxLayout()
        vis_row1.addWidget(QLabel("Provider 名称:"))
        self._vision_provider_input = QLineEdit()
        self._vision_provider_input.setPlaceholderText("如 ioasis / mozheyu / google")
        vis_row1.addWidget(self._vision_provider_input)
        vis_row1.addWidget(QLabel("Wire API:"))
        self._vision_wire_input = QLineEdit("chat")
        self._vision_wire_input.setPlaceholderText("chat 或 responses")
        vis_row1.addWidget(self._vision_wire_input)
        vis_layout.addLayout(vis_row1)

        vis_row2 = QHBoxLayout()
        vis_row2.addWidget(QLabel("API Key:"))
        self._vision_key_input = QLineEdit()
        self._vision_key_input.setEchoMode(QLineEdit.Password)
        vis_row2.addWidget(self._vision_key_input, stretch=1)
        vis_layout.addLayout(vis_row2)

        vis_row3 = QHBoxLayout()
        vis_row3.addWidget(QLabel("Base URL:"))
        self._vision_url_input = QLineEdit()
        self._vision_url_input.setPlaceholderText("https://generativelanguage.googleapis.com/v1beta/openai")
        vis_row3.addWidget(self._vision_url_input, stretch=1)
        self._scan_models_btn = QPushButton("扫描模型")
        self._scan_models_btn.setToolTip("从视觉 Provider 的 /models 端点获取可用模型列表")
        self._scan_models_btn.clicked.connect(self._on_scan_models)
        vis_row3.addWidget(self._scan_models_btn)
        vis_layout.addLayout(vis_row3)

        vis_row4 = QHBoxLayout()
        vis_row4.addWidget(QLabel("Reasoning effort:"))
        self._vision_reasoning_input = QLineEdit()
        self._vision_reasoning_input.setPlaceholderText("留空或 high")
        vis_row4.addWidget(self._vision_reasoning_input)
        self._vision_network_cb = QCheckBox("network_access")
        vis_row4.addWidget(self._vision_network_cb)
        self._vision_no_store_cb = QCheckBox("disable_response_storage")
        vis_row4.addWidget(self._vision_no_store_cb)
        vis_layout.addLayout(vis_row4)

        body_layout.addWidget(vis_group)

        # ---- 并发 ----
        conc_group = QGroupBox("并发 & 性能")
        conc_layout = QVBoxLayout(conc_group)

        conc_row = QHBoxLayout()
        conc_row.addWidget(QLabel("LLM 并发数:"))
        self._llm_parallel_input = QSpinBox()
        self._llm_parallel_input.setRange(0, 100)
        self._llm_parallel_input.setToolTip("0 = 自动")
        conc_row.addWidget(self._llm_parallel_input)
        conc_row.addWidget(QLabel("错峰间隔(秒):"))
        self._llm_stagger_input = QDoubleSpinBox()
        self._llm_stagger_input.setRange(0.0, 10.0)
        self._llm_stagger_input.setDecimals(1)
        self._llm_stagger_input.setSingleStep(0.1)
        conc_row.addWidget(self._llm_stagger_input)
        conc_row.addStretch()
        conc_layout.addLayout(conc_row)

        batch_row = QHBoxLayout()
        batch_row.addWidget(QLabel("每批图片数 (PDF/板书):"))
        self._processing_batch_input = QSpinBox()
        self._processing_batch_input.setRange(1, 50)
        self._processing_batch_input.setValue(self._cfg.processing.batch_size)
        self._processing_batch_input.setToolTip("每批发给视觉模型的图片数量；越大越快但 token 消耗越高")
        batch_row.addWidget(self._processing_batch_input)
        batch_row.addWidget(QLabel("视频帧批大小:"))
        self._video_batch_input = QSpinBox()
        self._video_batch_input.setRange(1, 50)
        self._video_batch_input.setValue(self._cfg.video.batch_size)
        self._video_batch_input.setToolTip("视频帧每批发送数；kimi-k2.5 实测支持 20 张")
        batch_row.addWidget(self._video_batch_input)
        batch_row.addStretch()
        conc_layout.addLayout(batch_row)

        body_layout.addWidget(conc_group)

        # ---- API 池 ----
        pool_group = QGroupBox("API 池 / 付费模式")
        pool_layout = QVBoxLayout(pool_group)

        pool_row = QHBoxLayout()
        self._paid_mode_cb = QCheckBox("付费模式（启用 API 池加速）")
        self._paid_mode_cb.setToolTip("启用后多个 API Key 并行工作")
        pool_row.addWidget(self._paid_mode_cb)
        pool_row.addWidget(QLabel("额外 API Key (逗号分隔):"))
        self._extra_keys_input = QLineEdit()
        self._extra_keys_input.setPlaceholderText("sk-xxx, sk-yyy, ...")
        self._extra_keys_input.setEchoMode(QLineEdit.Password)
        pool_row.addWidget(self._extra_keys_input, stretch=1)
        pool_layout.addLayout(pool_row)

        body_layout.addWidget(pool_group)

        body_layout.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll, stretch=1)

        # ---- 底部按钮 ----
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        ok_btn = QPushButton("应用设置")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._on_apply)
        bottom_row.addWidget(ok_btn)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        bottom_row.addWidget(cancel_btn)
        layout.addLayout(bottom_row)

    # ---- 后台拉取 ----

    def _wait_for_future(self, future):
        """Block the caller's return value but keep the Qt event loop pumping.

        Used by call sites that need a synchronous bool result (Apply-time
        validation gates) while still not freezing window repaints/clicks for
        the duration of the network call.
        """
        while not future.done():
            QApplication.processEvents()
            time.sleep(0.01)
        return future.result()

    def _run_fetch_async(self, fn, on_done):
        """Run a blocking network/subprocess call off the GUI thread.

        `fn` takes no arguments and returns a result or raises. `on_done(result,
        error)` is invoked on the GUI thread once `fn` finishes, so it is safe
        to touch widgets there. The rest of the window (and this dialog) stays
        responsive while `fn` runs; only the triggering control is disabled by
        the caller.
        """
        future = _FETCH_EXECUTOR.submit(fn)
        timer = QTimer(self)
        self._active_fetch_timers.append(timer)

        def _poll():
            if not future.done():
                return
            timer.stop()
            timer.deleteLater()
            if timer in self._active_fetch_timers:
                self._active_fetch_timers.remove(timer)
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001 - surfaced to on_done
                on_done(None, exc)
            else:
                on_done(result, None)

        timer.timeout.connect(_poll)
        timer.start(80)

    # ---- 扫描模型 ----

    def _on_scan_models(self):
        base_url = self._vision_url_input.text().strip()
        api_key = self._vision_key_input.text().strip()
        if not base_url:
            QMessageBox.warning(self, "缺少 Base URL", "请先填入视觉 Provider 的 Base URL。")
            return
        if not api_key:
            QMessageBox.warning(self, "缺少 API Key", "请先填入视觉 Provider 的 API Key。")
            return

        self._scan_models_btn.setEnabled(False)
        self._scan_models_btn.setText("扫描中...")

        def _fetch():
            return _scan_models_from_api(base_url, api_key)

        def _on_done(models, error):
            self._scan_models_btn.setEnabled(True)
            self._scan_models_btn.setText("扫描模型")
            if error is not None:
                logger.warning("扫描模型失败: %s", error)
                models = []
            if not models:
                QMessageBox.warning(self, "扫描失败",
                                    f"未能从 {base_url}/models 获取模型列表。\n"
                                    "请检查 Base URL 和 API Key 是否正确，或手动输入模型 ID。")
                return

            self._scanned_models = models
            current = self._vision_model_combo.currentText().strip()
            self._vision_model_combo.clear()
            self._vision_model_combo.addItems(models)
            if current and current in models:
                self._vision_model_combo.setCurrentText(current)
            elif models:
                self._vision_model_combo.setCurrentIndex(0)
            QMessageBox.information(self, "扫描完成",
                                    f"从视觉 Provider 获取到 {len(models)} 个模型。\n"
                                    "请从下拉菜单中选择模型。")

        self._run_fetch_async(_fetch, _on_done)

    def _populate_google_model_combos(self):
        vision_models = [m.name for m in model_catalog.load_google_vision_models()]
        audio_models = [m.name for m in model_catalog.load_google_audio_models()]
        if not vision_models:
            vision_models = [self._cfg.google_api.vision_model, "gemini-2.5-flash", "gemini-3.5-flash"]
        if not audio_models:
            audio_models = [self._cfg.google_api.audio_model, "gemini-3.5-flash", "gemini-3.1-pro"]

        current_v = normalize_google_ocr_vision_model(
            self._pending_google_vision_model or self._cfg.google_api.vision_model
        )
        current_a = self._pending_google_audio_model or self._cfg.google_api.audio_model
        self._google_vision_model_combo.blockSignals(True)
        self._google_audio_model_combo.blockSignals(True)
        try:
            self._google_vision_model_combo.clear()
            self._google_audio_model_combo.clear()
            self._google_vision_model_combo.addItems(list(dict.fromkeys(m for m in vision_models if m)))
            self._google_audio_model_combo.addItems(list(dict.fromkeys(m for m in audio_models if m)))
            self._google_vision_model_combo.setCurrentText(current_v)
            self._google_audio_model_combo.setCurrentText(current_a)
        finally:
            self._google_vision_model_combo.blockSignals(False)
            self._google_audio_model_combo.blockSignals(False)
        self._pending_google_vision_model = normalize_google_ocr_vision_model(
            self._google_vision_model_combo.currentText().strip()
        )
        self._pending_google_audio_model = self._google_audio_model_combo.currentText().strip()

    def _test_google_reachable(self, timeout: float) -> None:
        req = urllib.request.Request("https://www.google.com/generate_204", headers={"User-Agent": "OCRLLM"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status >= 500:
                raise RuntimeError(f"google.com 返回 HTTP {resp.status}")

    def _refresh_google_models(self, *, force: bool = False, notify: bool = False) -> bool:
        api_key = self._google_key_input.text().strip()
        if not api_key:
            if notify:
                QMessageBox.warning(self, "缺少 Google API Key", "请先填入 Google AI Studio API Key。")
            return False
        if not force and not model_catalog.google_model_cache_is_stale():
            self._populate_google_model_combos()
            return True

        self._refresh_google_models_btn.setEnabled(False)
        self._refresh_google_models_btn.setText("测试中...")

        def _fetch():
            timeout = float(self._cfg.google_api.network_check_timeout_seconds)
            self._test_google_reachable(timeout)
            return model_catalog.refresh_google_models(
                api_key,
                timeout=float(self._cfg.google_api.model_fetch_timeout_seconds),
            )

        try:
            summary = self._wait_for_future(_FETCH_EXECUTOR.submit(_fetch))
            self._populate_google_model_combos()
        except Exception as exc:
            logger.warning("Google 模型刷新失败: %s", exc)
            if notify:
                QMessageBox.warning(
                    self,
                    "Google 网络或模型拉取失败",
                    f"未能完成 google.com 连通性测试或实时模型拉取：\n{exc}",
                )
            return False
        finally:
            self._refresh_google_models_btn.setEnabled(True)
            self._refresh_google_models_btn.setText("测试网络并拉取模型")

        if notify:
            QMessageBox.information(
                self,
                "Google 模型刷新完成",
                f"获取到 {summary.raw_count} 个模型；已识别视觉 {len(summary.vision)} 个、长音频 {len(summary.audio)} 个。",
            )
        return True

    def _validate_google_environment_if_needed(self, *, force: bool = False) -> bool:
        if not self._google_enabled_cb.isChecked() and not force:
            return True
        if self._refresh_google_models(force=force, notify=False):
            return True
        answer = QMessageBox.question(
            self,
            "Google 网络测试失败",
            "当前网络环境未能访问 google.com 或未能实时拉取 Gemini 模型。\n\n"
            "建议先配置网络环境，然后重新测试。是否仍然强行继续保存谷歌模式？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def _refresh_bailian_models(self, *, force: bool = False, notify: bool = False) -> bool:
        api_key = self._api_key_input.text().strip()
        base_url = self._base_url_input.text().strip() or self._cfg.api.base_url
        if not api_key:
            if notify:
                QMessageBox.warning(self, "缺少 API Key", "请先填入 DashScope 主 API Key。")
            return False
        if not model_catalog.is_dashscope_base_url(base_url):
            if notify:
                QMessageBox.warning(self, "不是百炼地址", "主 API Base URL 看起来不是阿里云百炼 / DashScope 地址。")
            return False
        if not force and not model_catalog.bailian_model_cache_is_stale():
            return True

        self._refresh_dashscope_models_btn.setEnabled(False)
        self._refresh_dashscope_models_btn.setText("刷新中...")
        try:
            summary = self._wait_for_future(
                _FETCH_EXECUTOR.submit(model_catalog.refresh_bailian_models, base_url, api_key, timeout=15.0)
            )
        except Exception as exc:
            logger.warning("百炼模型刷新失败: %s", exc)
            if notify:
                QMessageBox.warning(self, "刷新失败", f"未能从百炼真实获取模型列表：\n{exc}")
            return False
        finally:
            self._refresh_dashscope_models_btn.setEnabled(True)
            self._refresh_dashscope_models_btn.setText("刷新百炼模型")

        # Actually load the fetched models into the picker, not just a count.
        current = self._vision_model_combo.currentText().strip()
        merged_names = [m.name for m in model_catalog.list_vision_models()]
        self._vision_model_combo.blockSignals(True)
        self._vision_model_combo.clear()
        self._vision_model_combo.addItems(merged_names)
        self._vision_model_combo.blockSignals(False)
        if current and current in merged_names:
            self._vision_model_combo.setCurrentText(current)
        elif current:
            self._vision_model_combo.setCurrentText(current)
        self._refresh_model_labels()

        if notify:
            QMessageBox.information(
                self,
                "刷新完成",
                f"获取到 {summary.raw_count} 个模型；已识别视觉 {len(summary.vision)} 个、音频 {len(summary.audio)} 个。\n"
                "视觉模型下拉框已更新为真实列表。",
            )
        return True

    def _on_vision_model_text_changed(self, text: str):
        self._pending_vision_model = text.strip()

    # ---- Codex 本机识图 ----

    def _codex_model(self) -> str:
        return normalize_codex_vision_model(self._codex_model_combo.currentText())

    def _on_codex_enabled_changed(self, checked: bool):
        if not self._restoring_settings:
            current = self._vision_model_combo.currentText().strip() or self._pending_vision_model
            if checked and current and current != self._codex_model():
                self._previous_non_codex_vision_model = current
            elif not checked and self._previous_non_codex_vision_model:
                self._pending_vision_model = self._previous_non_codex_vision_model
                self._vision_model_combo.setCurrentText(self._pending_vision_model)
        self._apply_codex_ui_state()

    def _on_vision_enabled_changed(self, checked: bool):
        """Refresh control state after the independent visual provider toggle changes."""
        self._apply_codex_ui_state()

    def _on_google_enabled_changed(self, checked: bool):
        """Refresh Google model discovery without changing the visual provider choice."""
        if (
            checked
            and not self._restoring_settings
            and self._google_key_input.text().strip()
        ):
            self._refresh_google_models(force=False, notify=True)
        self._apply_codex_ui_state()

    def _on_codex_model_changed(self, _text: str):
        if self._codex_enabled_cb.isChecked():
            self._pending_vision_model = self._codex_model()
            self._vision_model_combo.setCurrentText(self._pending_vision_model)

    def _apply_codex_ui_state(self):
        codex = self._codex_enabled_cb.isChecked()
        self._codex_model_combo.setEnabled(True)
        self._codex_reasoning_combo.setEnabled(True)
        self._codex_command_input.setEnabled(True)
        self._codex_timeout_input.setEnabled(True)
        self._codex_parallel_input.setEnabled(True)
        self._codex_stagger_input.setEnabled(True)
        self._codex_vision_batch_input.setEnabled(True)
        self._codex_video_batch_input.setEnabled(True)
        self._codex_check_btn.setEnabled(True)

        self._api_key_input.setEnabled(True)
        self._api_key_toggle.setEnabled(True)
        self._base_url_input.setEnabled(True)
        self._refresh_dashscope_models_btn.setEnabled(True)

        self._vision_provider_input.setEnabled(True)
        self._vision_wire_input.setEnabled(True)
        self._vision_key_input.setEnabled(True)
        self._vision_url_input.setEnabled(True)
        self._vision_reasoning_input.setEnabled(True)
        self._vision_network_cb.setEnabled(True)
        self._vision_no_store_cb.setEnabled(True)
        self._scan_models_btn.setEnabled(True)

        self._vision_model_combo.setEnabled(not codex)
        self._btn_pick_vision.setEnabled(not codex)
        self._model_queue_list.setEnabled(not codex)
        if codex:
            self._pending_vision_model = self._codex_model()
            self._vision_model_combo.setCurrentText(self._pending_vision_model)

    def _codex_config_from_ui(self):
        from OCRLLM.config import CodexVisionConfig
        return CodexVisionConfig(
            enabled=self._codex_enabled_cb.isChecked(),
            command=self._codex_command_input.text().strip() or "codex",
            model=self._codex_model(),
            reasoning_effort=self._codex_reasoning_combo.currentText().strip() or CODEX_VISION_DEFAULT_REASONING,
            timeout_seconds=self._codex_timeout_input.value(),
            parallel_requests=self._codex_parallel_input.value(),
            request_stagger_seconds=self._codex_stagger_input.value(),
            vision_batch_size=self._codex_vision_batch_input.value(),
            video_frame_batch_size=self._codex_video_batch_input.value(),
        )

    def _codex_check_signature(self) -> str:
        cfg = self._codex_config_from_ui()
        return f"{cfg.command}|{cfg.model}|{cfg.reasoning_effort}|{cfg.timeout_seconds}"

    def _validate_codex_environment_if_needed(self, *, force: bool = False) -> bool:
        if not self._codex_enabled_cb.isChecked() and not force:
            return True
        signature = self._codex_check_signature()
        if not force and self._settings.value("ui/codex_checked_signature", type=str) == signature:
            return True
        report = self._wait_for_future(_FETCH_EXECUTOR.submit(inspect_codex_cli, self._codex_config_from_ui()))
        if not report.ok:
            QMessageBox.warning(self, "Codex 不可用", report.message)
            return False
        self._settings.setValue("ui/codex_checked_signature", signature)
        self._settings.sync()
        return True

    def _on_codex_check_clicked(self):
        self._codex_check_btn.setEnabled(False)
        self._codex_check_btn.setText("检测中...")
        cfg = self._codex_config_from_ui()

        def _on_done(report, error):
            self._codex_check_btn.setEnabled(True)
            self._codex_check_btn.setText("检测 Codex")
            if error is not None:
                QMessageBox.warning(self, "Codex 不可用", str(error))
                return
            if report.ok:
                self._settings.setValue("ui/codex_checked_signature", self._codex_check_signature())
                self._settings.sync()
                QMessageBox.information(self, "Codex 检测通过", report.message)
            else:
                QMessageBox.warning(self, "Codex 不可用", report.message)

        self._run_fetch_async(lambda: inspect_codex_cli(cfg), _on_done)

    # ---- 模型降级队列操作 ----

    def _get_queue_items(self) -> list[str]:
        """获取当前队列中的所有模型名（按显示顺序）。"""
        items = []
        for i in range(self._model_queue_list.count()):
            items.append(self._model_queue_list.item(i).text())
        return items

    def _set_queue_items(self, items: list[str]):
        """设置队列内容。"""
        self._model_queue_list.clear()
        for item in items:
            self._model_queue_list.addItem(item)

    def _on_queue_add_scanned(self):
        """从扫描模型下拉框中选择模型添加到队列末尾。"""
        current = self._vision_model_combo.currentText().strip()
        if not current:
            QMessageBox.warning(self, "未选择模型", "请先从主模型下拉框中选择或输入一个模型 ID。")
            return
        existing = set(self._get_queue_items())
        if current in existing:
            QMessageBox.information(self, "已存在", f"模型 \"{current}\" 已在队列中。")
            return
        self._model_queue_list.addItem(current)

    def _on_queue_select_all(self):
        """将扫描到的所有模型全部加入队列（按扫描顺序）。"""
        if not self._scanned_models:
            QMessageBox.warning(self, "无扫描结果", '请先点击「扫描模型」获取可用模型列表。')
            return
        existing = set(self._get_queue_items())
        added = 0
        for m in self._scanned_models:
            if m not in existing:
                self._model_queue_list.addItem(m)
                existing.add(m)
                added += 1
        if added == 0:
            QMessageBox.information(self, "提示", "所有扫描模型已在队列中。")
        else:
            QMessageBox.information(self, "已添加", f"已将 {added} 个模型加入降级队列。")

    def _on_queue_remove(self):
        """移除队列中选中的模型。"""
        for item in self._model_queue_list.selectedItems():
            self._model_queue_list.takeItem(self._model_queue_list.row(item))

    def _on_queue_move_up(self):
        """将选中模型上移一位。"""
        row = self._model_queue_list.currentRow()
        if row <= 0:
            return
        item = self._model_queue_list.takeItem(row)
        self._model_queue_list.insertItem(row - 1, item)
        self._model_queue_list.setCurrentRow(row - 1)

    def _on_queue_move_down(self):
        """将选中模型下移一位。"""
        row = self._model_queue_list.currentRow()
        if row < 0 or row >= self._model_queue_list.count() - 1:
            return
        item = self._model_queue_list.takeItem(row)
        self._model_queue_list.insertItem(row + 1, item)
        self._model_queue_list.setCurrentRow(row + 1)

    # ---- QSettings 持久化 ----

    def _restore_from_settings(self):
        self._restoring_settings = True
        if self._settings.contains("ui/api_key"):
            self._api_key_input.setText(self._settings.value("ui/api_key", type=str) or "")
        else:
            self._api_key_input.setText(self._cfg.api.api_key)
        if self._settings.contains("ui/base_url"):
            self._base_url_input.setText(self._settings.value("ui/base_url", type=str) or "")
        else:
            self._base_url_input.setText(self._cfg.api.base_url)
        # Google Gemini
        if self._settings.contains("ui/google_api_enabled"):
            self._google_enabled_cb.setChecked(self._settings.value("ui/google_api_enabled", type=bool))
        else:
            self._google_enabled_cb.setChecked(self._cfg.google_api.enabled)
        if self._settings.contains("ui/google_api_key"):
            self._google_key_input.setText(self._settings.value("ui/google_api_key", type=str) or "")
        else:
            self._google_key_input.setText(self._cfg.google_api.api_key)
        if self._settings.contains("ui/google_vision_model"):
            self._pending_google_vision_model = self._settings.value("ui/google_vision_model", type=str) or self._pending_google_vision_model
        if self._settings.contains("ui/google_audio_model"):
            self._pending_google_audio_model = self._settings.value("ui/google_audio_model", type=str) or self._pending_google_audio_model
        self._populate_google_model_combos()
        if self._settings.contains("ui/google_parallel_requests"):
            self._google_parallel_input.setValue(int(self._settings.value("ui/google_parallel_requests")))
        else:
            self._google_parallel_input.setValue(self._cfg.google_api.parallel_requests)
        if self._settings.contains("ui/google_request_stagger_seconds"):
            self._google_stagger_input.setValue(float(self._settings.value("ui/google_request_stagger_seconds")))
        else:
            self._google_stagger_input.setValue(self._cfg.google_api.request_stagger_seconds)
        if self._settings.contains("ui/google_vision_batch_size"):
            self._google_vision_batch_input.setValue(int(self._settings.value("ui/google_vision_batch_size")))
        else:
            self._google_vision_batch_input.setValue(self._cfg.google_api.vision_batch_size)
        if self._settings.contains("ui/google_video_frame_batch_size"):
            self._google_video_batch_input.setValue(int(self._settings.value("ui/google_video_frame_batch_size")))
        else:
            self._google_video_batch_input.setValue(self._cfg.google_api.video_frame_batch_size)
        # Codex 本机识图
        if self._settings.contains("ui/codex_vision_enabled"):
            self._codex_enabled_cb.setChecked(self._settings.value("ui/codex_vision_enabled", type=bool))
        if self._settings.contains("ui/codex_command"):
            self._codex_command_input.setText(self._settings.value("ui/codex_command", type=str) or "codex")
        codex_model = CODEX_VISION_DEFAULT_MODEL
        if self._settings.contains("ui/codex_model"):
            codex_model = migrate_stored_codex_vision_model(self._settings.value("ui/codex_model", type=str))
        self._codex_model_combo.setCurrentText(codex_model)
        if self._settings.contains("ui/codex_reasoning_effort"):
            self._codex_reasoning_combo.setCurrentText(self._settings.value("ui/codex_reasoning_effort", type=str) or CODEX_VISION_DEFAULT_REASONING)
        if self._settings.contains("ui/codex_timeout_seconds"):
            self._codex_timeout_input.setValue(int(self._settings.value("ui/codex_timeout_seconds")))
        else:
            self._codex_timeout_input.setValue(self._cfg.codex_vision.timeout_seconds)
        if self._settings.contains("ui/codex_parallel_requests"):
            self._codex_parallel_input.setValue(int(self._settings.value("ui/codex_parallel_requests")))
        else:
            self._codex_parallel_input.setValue(self._cfg.codex_vision.parallel_requests)
        if self._settings.contains("ui/codex_request_stagger_seconds"):
            self._codex_stagger_input.setValue(float(self._settings.value("ui/codex_request_stagger_seconds")))
        else:
            self._codex_stagger_input.setValue(self._cfg.codex_vision.request_stagger_seconds)
        if self._settings.contains("ui/codex_vision_batch_size"):
            self._codex_vision_batch_input.setValue(int(self._settings.value("ui/codex_vision_batch_size")))
        else:
            self._codex_vision_batch_input.setValue(self._cfg.codex_vision.vision_batch_size)
        if self._settings.contains("ui/codex_video_frame_batch_size"):
            self._codex_video_batch_input.setValue(int(self._settings.value("ui/codex_video_frame_batch_size")))
        else:
            self._codex_video_batch_input.setValue(self._cfg.codex_vision.video_frame_batch_size)
        if self._settings.contains("ui/vision_model_before_codex"):
            self._previous_non_codex_vision_model = self._settings.value("ui/vision_model_before_codex", type=str) or ""
        # 视觉 Provider
        if self._settings.contains("ui/vision_api_enabled"):
            self._vision_enabled_cb.setChecked(self._settings.value("ui/vision_api_enabled", type=bool))
        else:
            self._vision_enabled_cb.setChecked(self._cfg.vision_api.enabled)
        if self._settings.contains("ui/vision_provider"):
            self._vision_provider_input.setText(self._settings.value("ui/vision_provider", type=str) or "")
        else:
            self._vision_provider_input.setText(self._cfg.vision_api.provider)
        if self._settings.contains("ui/vision_api_key"):
            self._vision_key_input.setText(self._settings.value("ui/vision_api_key", type=str) or "")
        else:
            self._vision_key_input.setText(self._cfg.vision_api.api_key)
        if self._settings.contains("ui/vision_base_url"):
            self._vision_url_input.setText(self._settings.value("ui/vision_base_url", type=str) or "")
        else:
            self._vision_url_input.setText(self._cfg.vision_api.base_url)
        if self._settings.contains("ui/vision_wire_api"):
            self._vision_wire_input.setText(self._settings.value("ui/vision_wire_api", type=str) or "")
        else:
            self._vision_wire_input.setText(self._cfg.vision_api.wire_api)
        if self._settings.contains("ui/vision_reasoning_effort"):
            self._vision_reasoning_input.setText(self._settings.value("ui/vision_reasoning_effort", type=str) or "")
        else:
            self._vision_reasoning_input.setText(self._cfg.vision_api.model_reasoning_effort)
        if self._settings.contains("ui/vision_network_access"):
            self._vision_network_cb.setChecked(self._settings.value("ui/vision_network_access", type=bool))
        else:
            self._vision_network_cb.setChecked(self._cfg.vision_api.network_access)
        if self._settings.contains("ui/vision_disable_response_storage"):
            self._vision_no_store_cb.setChecked(self._settings.value("ui/vision_disable_response_storage", type=bool))
        else:
            self._vision_no_store_cb.setChecked(self._cfg.vision_api.disable_response_storage)
        if self._settings.contains("ui/vision_model"):
            saved = self._settings.value("ui/vision_model", type=str) or ""
            if saved:
                self._pending_vision_model = saved
                self._vision_model_combo.setCurrentText(saved)
        else:
            self._vision_model_combo.setCurrentText(self._pending_vision_model)
        if self._settings.contains("ui/audio_model"):
            self._pending_audio_model = self._settings.value("ui/audio_model", type=str) or ""
        self._refresh_model_labels()
        if self._settings.contains("ui/llm_parallel_requests"):
            self._llm_parallel_input.setValue(int(self._settings.value("ui/llm_parallel_requests")))
        else:
            self._llm_parallel_input.setValue(self._cfg.concurrency.llm_parallel_requests)
        if self._settings.contains("ui/llm_request_stagger_seconds"):
            self._llm_stagger_input.setValue(float(self._settings.value("ui/llm_request_stagger_seconds")))
        else:
            self._llm_stagger_input.setValue(self._cfg.concurrency.llm_request_stagger_seconds)
        if self._settings.contains("ui/paid_mode"):
            self._paid_mode_cb.setChecked(self._settings.value("ui/paid_mode", type=bool))
        else:
            self._paid_mode_cb.setChecked(self._cfg.api.paid_mode)
        if self._settings.contains("ui/extra_api_keys"):
            self._extra_keys_input.setText(self._settings.value("ui/extra_api_keys", type=str) or "")
        else:
            extra_keys = [key for key in self._cfg.api.api_keys if key and key != self._cfg.api.api_key]
            self._extra_keys_input.setText(", ".join(extra_keys))
        if self._settings.contains("ui/processing_batch_size"):
            self._processing_batch_input.setValue(int(self._settings.value("ui/processing_batch_size")))
        else:
            self._processing_batch_input.setValue(self._cfg.processing.batch_size)
        if self._settings.contains("ui/video_batch_size"):
            self._video_batch_input.setValue(int(self._settings.value("ui/video_batch_size")))
        else:
            self._video_batch_input.setValue(self._cfg.video.batch_size)
        # 模型降级队列
        if self._settings.contains("ui/vision_model_queue"):
            try:
                queue = json.loads(self._settings.value("ui/vision_model_queue", type=str) or "[]")
                self._set_queue_items(queue)
            except (json.JSONDecodeError, TypeError):
                self._set_queue_items([])
        else:
            self._set_queue_items(self._cfg.vision_api.vision_model_queue)
        self._restoring_settings = False
        self._apply_codex_ui_state()
        if not self._google_enabled_cb.isChecked():
            self._refresh_bailian_models(force=False, notify=False)

    def _persist_to_settings(self):
        self._pending_google_vision_model = (
            self._google_vision_model_combo.currentText().strip() or self._pending_google_vision_model
        )
        self._pending_google_audio_model = (
            self._google_audio_model_combo.currentText().strip() or self._pending_google_audio_model
        )
        self._pending_vision_model = (
            self._vision_model_combo.currentText().strip() or self._pending_vision_model
        )
        self._settings.setValue("ui/api_key", self._api_key_input.text())
        self._settings.setValue("ui/base_url", self._base_url_input.text())
        self._settings.setValue("ui/google_api_enabled", self._google_enabled_cb.isChecked())
        self._settings.setValue("ui/google_api_key", self._google_key_input.text())
        self._settings.setValue("ui/google_vision_model", normalize_google_ocr_vision_model(self._pending_google_vision_model))
        self._settings.setValue("ui/google_audio_model", self._pending_google_audio_model)
        self._settings.setValue("ui/google_parallel_requests", self._google_parallel_input.value())
        self._settings.setValue("ui/google_request_stagger_seconds", self._google_stagger_input.value())
        self._settings.setValue("ui/google_vision_batch_size", self._google_vision_batch_input.value())
        self._settings.setValue("ui/google_video_frame_batch_size", self._google_video_batch_input.value())
        self._settings.setValue("ui/codex_vision_enabled", self._codex_enabled_cb.isChecked())
        self._settings.setValue("ui/codex_command", self._codex_command_input.text())
        self._settings.setValue("ui/codex_model", self._codex_model())
        self._settings.setValue("ui/codex_reasoning_effort", self._codex_reasoning_combo.currentText().strip())
        self._settings.setValue("ui/codex_timeout_seconds", self._codex_timeout_input.value())
        self._settings.setValue("ui/codex_parallel_requests", self._codex_parallel_input.value())
        self._settings.setValue("ui/codex_request_stagger_seconds", self._codex_stagger_input.value())
        self._settings.setValue("ui/codex_vision_batch_size", self._codex_vision_batch_input.value())
        self._settings.setValue("ui/codex_video_frame_batch_size", self._codex_video_batch_input.value())
        self._settings.setValue("ui/vision_model_before_codex", self._previous_non_codex_vision_model)
        self._settings.setValue("ui/vision_api_enabled", self._vision_enabled_cb.isChecked())
        self._settings.setValue("ui/vision_provider", self._vision_provider_input.text())
        self._settings.setValue("ui/vision_api_key", self._vision_key_input.text())
        self._settings.setValue("ui/vision_base_url", self._vision_url_input.text())
        self._settings.setValue("ui/vision_wire_api", self._vision_wire_input.text())
        self._settings.setValue("ui/vision_reasoning_effort", self._vision_reasoning_input.text())
        self._settings.setValue("ui/vision_network_access", self._vision_network_cb.isChecked())
        self._settings.setValue("ui/vision_disable_response_storage", self._vision_no_store_cb.isChecked())
        self._settings.setValue("ui/vision_model", self._pending_vision_model)
        self._settings.setValue("ui/audio_model", self._pending_audio_model)
        self._settings.setValue("ui/llm_parallel_requests", self._llm_parallel_input.value())
        self._settings.setValue("ui/llm_request_stagger_seconds", self._llm_stagger_input.value())
        self._settings.setValue("ui/paid_mode", self._paid_mode_cb.isChecked())
        self._settings.setValue("ui/extra_api_keys", self._extra_keys_input.text())
        self._settings.setValue("ui/processing_batch_size", self._processing_batch_input.value())
        self._settings.setValue("ui/video_batch_size", self._video_batch_input.value())
        # 模型降级队列
        queue = self._get_queue_items()
        self._settings.setValue("ui/vision_model_queue", json.dumps(queue, ensure_ascii=False))
        self._settings.sync()

    # ---- 模型选择 ----

    def _live_dashscope_fetch(self):
        """Real /models fetch used by the picker's own "拉取最新模型" button."""
        api_key = self._api_key_input.text().strip()
        base_url = self._base_url_input.text().strip() or self._cfg.api.base_url
        if not api_key:
            raise RuntimeError("请先在上方填入 DashScope API Key")
        if not model_catalog.is_dashscope_base_url(base_url):
            raise RuntimeError("主 API Base URL 不是百炼/DashScope 地址，无法用此端点拉取")
        model_catalog.refresh_bailian_models(base_url, api_key, timeout=15.0)

    def _open_vision_picker(self):
        from OCRLLM.gui.model_picker import ModelPickerDialog

        def _validate_custom(name: str) -> bool:
            from OCRLLM.gui.model_validator import _validate_vision
            from OCRLLM.core.llm_client import LLMClient
            updates, info = self._read_overrides()
            if not info["new_key"] and not info["vision_api_key"]:
                QMessageBox.warning(self, "缺少 API Key", "请先填入 API Key 再测试自定义模型。")
                return False
            temp_cfg = self._cfg.with_updates(**updates)
            client = LLMClient(cfg=temp_cfg)
            return _validate_vision(self, client, name)

        dlg = ModelPickerDialog(self, kind="vision",
                                current_name=self._pending_vision_model,
                                on_validate_custom=_validate_custom,
                                on_fetch_live=self._live_dashscope_fetch)
        if dlg.exec_() == ModelPickerDialog.Accepted:
            self._pending_vision_model = dlg.selected_model_name
            self._vision_model_combo.setCurrentText(dlg.selected_model_name)
            self._refresh_model_labels()

    def _open_audio_picker(self):
        from OCRLLM.gui.model_picker import ModelPickerDialog

        def _validate_custom(name: str) -> bool:
            from OCRLLM.gui.model_validator import _validate_audio
            from OCRLLM.core.llm_client import LLMClient
            api_key = self._api_key_input.text().strip()
            if not api_key:
                QMessageBox.warning(self, "缺少 API Key", "请先填入 API Key 再测试自定义模型。")
                return False
            temp_cfg = self._cfg.with_updates(
                api={"api_key": api_key,
                     "base_url": self._base_url_input.text().strip() or self._cfg.api.base_url})
            client = LLMClient(cfg=temp_cfg)
            return _validate_audio(self, client, name)

        dlg = ModelPickerDialog(self, kind="audio",
                                current_name=self._pending_audio_model,
                                on_validate_custom=_validate_custom,
                                on_fetch_live=self._live_dashscope_fetch)
        if dlg.exec_() == ModelPickerDialog.Accepted:
            self._pending_audio_model = dlg.selected_model_name
            self._refresh_model_labels()

    def _refresh_model_labels(self):
        a = self._pending_audio_model or "—"
        meta_a = model_catalog.find_audio_model(self._pending_audio_model)
        if meta_a:
            a = model_catalog.display_label(meta_a)
        self._audio_model_label.setText(a)

    # ---- 读取 / 应用 ----

    def _read_overrides(self) -> tuple[dict, dict]:
        codex_enabled = self._codex_enabled_cb.isChecked()
        google_enabled = self._google_enabled_cb.isChecked()
        new_key = self._api_key_input.text().strip()
        new_url = self._base_url_input.text().strip()
        vis_enabled = self._vision_enabled_cb.isChecked()
        vis_provider = self._vision_provider_input.text().strip()
        vis_key = self._vision_key_input.text().strip()
        vis_url = self._vision_url_input.text().strip()
        vis_wire = (self._vision_wire_input.text().strip() or "chat").lower()
        vis_reasoning = self._vision_reasoning_input.text().strip()
        vis_network = self._vision_network_cb.isChecked()
        vis_no_store = self._vision_no_store_cb.isChecked()
        vision_model = self._pending_vision_model
        audio_model = self._pending_audio_model
        new_parallel = self._llm_parallel_input.value()
        new_stagger = self._llm_stagger_input.value()
        processing_batch = self._processing_batch_input.value()
        video_batch = self._video_batch_input.value()
        paid_mode = self._paid_mode_cb.isChecked()
        extra_keys_text = self._extra_keys_input.text().strip()
        google_key = self._google_key_input.text().strip()
        google_vision_model = normalize_google_ocr_vision_model(
            self._google_vision_model_combo.currentText().strip() or self._pending_google_vision_model
        )
        google_audio_model = self._google_audio_model_combo.currentText().strip() or self._pending_google_audio_model
        codex_parallel = self._codex_parallel_input.value()
        codex_stagger = self._codex_stagger_input.value()
        codex_vision_batch = self._codex_vision_batch_input.value()
        codex_video_batch = self._codex_video_batch_input.value()

        api_keys = [new_key] if new_key else []
        if extra_keys_text:
            for k in extra_keys_text.split(","):
                k = k.strip()
                if k and k != new_key:
                    api_keys.append(k)

        models_update: dict = {}
        if vision_model:
            models_update["vision_model"] = vision_model
            if not vis_enabled:
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
                "parallel_requests": self._google_parallel_input.value(),
                "request_stagger_seconds": self._google_stagger_input.value(),
                "vision_batch_size": self._google_vision_batch_input.value(),
                "video_frame_batch_size": self._google_video_batch_input.value(),
                "api_keys": [google_key] if google_key else [],
            },
            "codex_vision": {
                "enabled": codex_enabled,
                "command": self._codex_command_input.text().strip() or "codex",
                "model": self._codex_model(),
                "reasoning_effort": self._codex_reasoning_combo.currentText().strip() or CODEX_VISION_DEFAULT_REASONING,
                "timeout_seconds": self._codex_timeout_input.value(),
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
                "vision_model_queue": self._get_queue_items(),
            },
            "concurrency": {
                "llm_parallel_requests": codex_parallel if codex_enabled else new_parallel,
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
            "vision_api_enabled": vis_enabled,
            "vision_provider": vis_provider,
            "vision_api_key": vis_key,
            "vision_base_url": vis_url,
            "vision_wire_api": vis_wire,
            "auto_vision_model": False,
            "new_parallel": codex_parallel if codex_enabled else new_parallel,
            "new_stagger": codex_stagger if codex_enabled else new_stagger,
            "paid_mode": paid_mode, "api_keys": api_keys,
        }
        return updates, info

    def _on_apply(self):
        _updates, info = self._read_overrides()

        if info["google_api_enabled"]:
            if not info["google_api_key"]:
                QMessageBox.warning(self, "提示", "启用谷歌模式时，Google API Key 不能为空")
                return
            if not self._validate_google_environment_if_needed(force=True):
                return
        if self._codex_enabled_cb.isChecked():
            if not self._validate_codex_environment_if_needed(force=True):
                return
        if not info["google_api_enabled"] and not self._codex_enabled_cb.isChecked() and not info["new_key"] and not info["vision_api_enabled"]:
            QMessageBox.warning(self, "提示", "API Key 不能为空")
            return

        if info["vision_api_enabled"] and not self._codex_enabled_cb.isChecked():
            if info["vision_wire_api"] not in {"chat", "responses"}:
                QMessageBox.warning(self, "提示", "视觉 Wire API 只能是 chat 或 responses")
                return
            if not info["vision_api_key"] or not self._vision_url_input.text().strip():
                QMessageBox.warning(self, "提示", "启用视觉独立 Provider 时，视觉 API Key 和 Base URL 不能为空")
                return

        if not info["google_api_enabled"]:
            self._refresh_bailian_models(force=False, notify=False)
        self._persist_to_settings()
        self.accept()
