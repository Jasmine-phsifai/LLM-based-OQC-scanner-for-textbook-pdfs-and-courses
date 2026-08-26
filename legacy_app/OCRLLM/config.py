"""
OCRLLM 全局配置。

配置拆成多个子域，统一使用嵌套 section 访问和更新，避免单个 dataclass 持续膨胀。
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from OCRLLM.core.codex_model_catalog import (
    CODEX_VISION_DEFAULT_MODEL as DEFAULT_CODEX_VISION_MODEL,
    normalize_codex_vision_model,
)


# 历史遗留：旧 GUI / 旧测试可能 import VISION_MODEL_OPTIONS。
# 真正的模型清单现在维护在 OCRLLM.core.model_catalog 里。
def _legacy_vision_options() -> tuple[str, ...]:
    try:
        from OCRLLM.core.model_catalog import BUILTIN_VISION_MODELS
        return tuple(m.name for m in BUILTIN_VISION_MODELS if m.kind == "vlm")
    except Exception:
        return ("qwen-vl-max", "qwen-vl-plus", "qwen3-vl-plus", "qwen3-vl-flash")


VISION_MODEL_OPTIONS = _legacy_vision_options()

DEFAULT_GOOGLE_OCR_VISION_MODEL = "gemini-2.5-flash"
DEFAULT_CODEX_VISION_REASONING_EFFORT = "medium"
CODEX_VISION_RUNTIME_BATCH_SIZE = 5
CODEX_VISION_RUNTIME_PARALLEL = 2
CODEX_VISION_RUNTIME_STAGGER_SECONDS = 0.5
CODEX_VISION_RUNTIME_VIDEO_BATCH_SIZE = 5


def normalize_google_ocr_vision_model(model: str | None) -> str:
    value = (model or "").strip()
    if not value:
        return DEFAULT_GOOGLE_OCR_VISION_MODEL
    lowered = value.lower()
    if "image" in lowered or "imagen" in lowered or "nano-banana" in lowered:
        return DEFAULT_GOOGLE_OCR_VISION_MODEL
    return value


def _default_home_dir() -> Path:
    """默认的 OCRLLM 主目录。

    ``Path.home()`` 在没有 HOME/USERPROFILE 的环境（服务账号、被清空的子进程环境）
    里直接抛 RuntimeError，不能让它拖垮整个配置构造。
    """
    try:
        return Path.home() / "OCRLLM"
    except RuntimeError:
        return Path(tempfile.gettempdir()) / "OCRLLM"


def _existing_legacy_data_root() -> Path | None:
    """已有历史数据（检查点/输出）的老数据根目录。

    默认目录曾从安装目录迁到 ~/OCRLLM，导致老安装的检查点对应用不可见、
    断点续传横幅消失。若旧数据根仍持有检查点，就继续沿用它。
    """
    here = Path(__file__).resolve()
    candidates = []
    if len(here.parents) >= 3:
        candidates.append(here.parents[2])  # 仓库根（历史真实数据位置）
    candidates.append(here.parent)  # 旧默认 <package>/output
    for root in candidates:
        try:
            if (root / "output" / ".checkpoints").is_dir():
                return root
        except OSError:
            continue
    return None


@dataclass
class APIConfig:
    """API 连接配置（密钥、地址、付费模式）。"""
    api_key: str = field(
        default_factory=lambda: os.environ.get(
            "DASHSCOPE_API_KEY",
            "",
        )
    )
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    paid_mode: bool = False
    api_keys: list[str] = field(default_factory=list)


@dataclass
class VisionAPIConfig:
    """视觉模型可选的独立 OpenAI-compatible Provider 配置。

    留空/禁用时，图片、PDF、视频帧识别沿用 api 段；启用后仅视觉请求切到这里，
    长音频 filetrans 仍使用 DashScope api 段。

    vision_model_queue: 模型降级队列，当主模型（models.vision_model）额度耗尽时，
    按队列顺序依次尝试下一个模型。仅用于 OpenAI 兼容视觉 Provider。
    """
    enabled: bool = False
    provider: str = ""
    api_key: str = ""
    base_url: str = ""
    wire_api: str = "chat"  # "chat" 或 "responses"
    model_reasoning_effort: str = ""
    network_access: bool = False
    disable_response_storage: bool = True
    advance_queue_on_retriable_errors: bool = False
    vision_model_queue: list[str] = field(default_factory=list)


@dataclass
class CodexVisionConfig:
    """本机 Codex CLI 视觉识别配置。"""
    enabled: bool = False
    command: str = "codex"
    model: str = DEFAULT_CODEX_VISION_MODEL
    reasoning_effort: str = DEFAULT_CODEX_VISION_REASONING_EFFORT
    fast_mode: bool = False
    timeout_seconds: int = 1800
    parallel_requests: int = CODEX_VISION_RUNTIME_PARALLEL
    request_stagger_seconds: float = CODEX_VISION_RUNTIME_STAGGER_SECONDS
    vision_batch_size: int = CODEX_VISION_RUNTIME_BATCH_SIZE
    video_frame_batch_size: int = CODEX_VISION_RUNTIME_VIDEO_BATCH_SIZE


@dataclass
class GoogleAPIConfig:
    """Google AI Studio / Gemini SDK 模式配置。

    该模式独立于 DashScope / OpenAI-compatible 视觉 Provider。启用后，
    PDF/图片/视频帧和音频识别优先走 Google SDK；DashScope 主 API 保留但不参与
    本次管线。并发和批大小独立配置，避免 Google 多模态能力被 Qwen 默认上限限制。
    """
    enabled: bool = False
    api_key: str = field(
        default_factory=lambda: os.environ.get(
            "GOOGLE_API_KEY",
            os.environ.get("GEMINI_API_KEY", ""),
        )
    )
    text_model: str = "gemini-3.5-flash"
    vision_model: str = DEFAULT_GOOGLE_OCR_VISION_MODEL
    audio_model: str = "gemini-3.1-pro-preview"
    vision_model_queue: list[str] = field(default_factory=list)
    audio_model_queue: list[str] = field(default_factory=list)
    api_keys: list[str] = field(default_factory=list)
    parallel_requests: int = 16
    request_stagger_seconds: float = 1.0
    vision_batch_size: int = 20
    video_frame_batch_size: int = 20
    audio_chunk_seconds: int = 30 * 60
    audio_overlap_seconds: int = 30
    network_check_timeout_seconds: float = 8.0
    model_fetch_timeout_seconds: float = 20.0
    allow_force_continue_after_network_warning: bool = False


@dataclass
class ModelConfig:
    """模型名称配置。

    `vision_model` ：图片/截图/PDF/视频帧识别用的模型（VLM 或 omni）。
    `text_model`   ：纯文本任务用的模型，一般跟 vision_model 同一个或 flash 系列。
    `asr_model`    ：长录音异步识别（filetrans）模型。GUI 中的"音频模型"下拉控制此项。
    `asr_short_model` ：短录音同步模型，用于 <5min 音频；GUI 不直接暴露，
                       由系统在 audio_model 选定后自动派生（asr_long → 默认 short_model）。
    `allow_asr_short_fallback` ：旧保留开关。filetrans 的长音频失败不会自动转成短 ASR。
    """
    vision_model: str = "qwen-vl-max"
    text_model: str = "qwen-vl-plus"
    asr_model: str = "qwen3-asr-flash-filetrans"
    asr_short_model: str = "qwen3-asr-flash"
    allow_asr_short_fallback: bool = False


@dataclass
class ProcessingConfig:
    """处理参数配置（批量大小、DPI、图像质量等）。"""
    batch_size: int = 10
    pdf_dpi: int = 200
    image_quality: int = 90
    image_max_side: int = 2048
    asr_short_chunk_seconds: int = 290
    asr_fallback_chunk_seconds: int = 360
    asr_fallback_context_seconds: int = 30


@dataclass
class ConcurrencyConfig:
    """并发参数配置（渲染线程、LLM 并行数、错峰间隔等）。"""
    pdf_render_workers: int = 0
    llm_parallel_requests: int = 15
    llm_request_stagger_seconds: float = 0.5
    video_resize_workers: int = 0
    audio_split_workers: int = 0
    audio_asr_parallel_requests: int = 4


@dataclass
class PathConfig:
    """输出和临时文件路径配置。"""
    output_dir: str = ""
    temp_dir: str = ""


@dataclass
class VideoConfig:
    """视频处理参数配置（抽帧间隔和变化阈值等）。"""
    frame_interval: float = 5.0
    refine_interval: float = 2.0
    change_threshold: float = 0.15
    drift_threshold: float = 0.10
    max_segment_sec: float = 150.0
    min_content_ratio: float = 0.005
    phash_threshold: int = 3
    target_frames_per_hour: float = 40.0
    batch_size: int = 4
    extract_hotwords_with_text_model: bool = True


@dataclass
class ShotDetectionConfig:
    """场景切换检测参数配置（用于短视频抽帧）。"""
    backend: str = "scenedetect"           # "scenedetect" 或 "transnetv2"
    default_threshold: float = 0.3
    threshold_step: float = 0.05
    max_iterations: int = 8
    # 目标切换密度 (cuts/min)
    short_video_density_min: float = 5.0    # ≤2min 视频
    short_video_density_max: float = 35.0
    medium_video_density_min: float = 3.0   # 2-10min 视频
    medium_video_density_max: float = 20.0
    # 长短视频分界 (秒)
    long_video_threshold_sec: float = 600.0


@dataclass
class SocialConfig:
    """社交媒体下载与处理参数配置。"""
    download_format: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    cookies_file: str = ""                  # cookies.txt 路径，留空则不使用
    cookies_from_browser: str = ""          # 浏览器名称（chrome/firefox/edge），留空则不使用
    max_download_retries: int = 3
    concurrent_fragment_downloads: int = 4
    # 长短视频分类阈值 (秒)；与 ShotDetectionConfig.long_video_threshold_sec 保持一致
    long_short_boundary_sec: float = 600.0
    # 短视频帧截取：终点前偏移 (秒)
    end_frame_offset_sec: float = 0.2
    # 短视频 LLM batch size (帧/批)
    short_video_batch_size: int = 2
    # B站原生 API 相关
    bilibili_quality: int = 80              # 16=360P, 32=480P, 64=720P, 80=1080P
    fetch_danmaku: bool = True              # 获取弹幕
    fetch_comments: bool = True             # 获取评论
    comment_max_pages: int = 3              # 评论最大翻页数
    long_video_llm_parallel_requests: int = 4
    long_video_llm_request_stagger_seconds: float = 1.0


@dataclass
class AppConfig:
    """应用全局配置。"""

    api: APIConfig = field(default_factory=APIConfig)
    vision_api: VisionAPIConfig = field(default_factory=VisionAPIConfig)
    codex_vision: CodexVisionConfig = field(default_factory=CodexVisionConfig)
    google_api: GoogleAPIConfig = field(default_factory=GoogleAPIConfig)
    models: ModelConfig = field(default_factory=ModelConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    social: SocialConfig = field(default_factory=SocialConfig)
    shot_detection: ShotDetectionConfig = field(default_factory=ShotDetectionConfig)

    def __post_init__(self):
        # 默认输出/临时目录不能放在安装包目录里面：安装目录在其他机器上
        # 可能不可写（系统目录/共享安装），但已有历史检查点的老安装必须
        # 继续沿用旧目录，否则断点续传会“消失”。
        # 优先级：显式 PathConfig > OCRLLM_HOME > 已有数据的旧根 > ~/OCRLLM。
        env_home = os.environ.get("OCRLLM_HOME")
        if env_home:
            default_home = Path(env_home)
        else:
            default_home = _existing_legacy_data_root() or _default_home_dir()
        if not self.paths.output_dir:
            self.paths.output_dir = str(default_home / "output")
        if not self.paths.temp_dir:
            self.paths.temp_dir = str(default_home / "temp")

    @classmethod
    def from_env(cls) -> AppConfig:
        """从环境变量加载配置。"""
        cfg = cls()
        updates = {}
        def _env_bool(name: str) -> bool | None:
            raw = os.environ.get(name)
            if raw is None:
                return None
            return raw.strip().lower() in {"1", "true", "yes", "on"}
        def _env_int(name: str) -> int | None:
            raw = os.environ.get(name)
            if raw is None or not raw.strip():
                return None
            try:
                return int(raw)
            except ValueError:
                return None
        def _env_float(name: str) -> float | None:
            raw = os.environ.get(name)
            if raw is None or not raw.strip():
                return None
            try:
                return float(raw)
            except ValueError:
                return None

        key = os.environ.get("DASHSCOPE_API_KEY")
        if key:
            updates.setdefault("api", {})["api_key"] = key
        url = os.environ.get("DASHSCOPE_BASE_URL")
        if url:
            updates.setdefault("api", {})["base_url"] = url
        vision_key = os.environ.get("OCRLLM_VISION_API_KEY")
        if vision_key:
            updates.setdefault("vision_api", {})["api_key"] = vision_key
            updates.setdefault("vision_api", {})["enabled"] = True
        vision_url = os.environ.get("OCRLLM_VISION_BASE_URL")
        if vision_url:
            updates.setdefault("vision_api", {})["base_url"] = vision_url
            updates.setdefault("vision_api", {})["enabled"] = True
        vision_wire_api = os.environ.get("OCRLLM_VISION_WIRE_API")
        if vision_wire_api:
            updates.setdefault("vision_api", {})["wire_api"] = vision_wire_api
        vision_queue_on_errors = _env_bool("OCRLLM_VISION_ADVANCE_QUEUE_ON_RETRIABLE_ERRORS")
        if vision_queue_on_errors is not None:
            updates.setdefault("vision_api", {})["advance_queue_on_retriable_errors"] = vision_queue_on_errors
        vision_model = os.environ.get("OCRLLM_VISION_MODEL")
        if vision_model:
            updates.setdefault("models", {})["vision_model"] = vision_model
        codex_enabled = _env_bool("OCRLLM_CODEX_VISION_ENABLED")
        if codex_enabled is not None:
            updates.setdefault("codex_vision", {})["enabled"] = codex_enabled
        codex_command = os.environ.get("OCRLLM_CODEX_COMMAND")
        if codex_command:
            updates.setdefault("codex_vision", {})["command"] = codex_command
        codex_model = os.environ.get("OCRLLM_CODEX_MODEL")
        if codex_model:
            codex_model = normalize_codex_vision_model(codex_model)
            updates.setdefault("codex_vision", {})["model"] = codex_model
            updates.setdefault("models", {})["vision_model"] = codex_model
        codex_reasoning = os.environ.get("OCRLLM_CODEX_REASONING_EFFORT")
        if codex_reasoning:
            updates.setdefault("codex_vision", {})["reasoning_effort"] = codex_reasoning
        codex_fast_mode = _env_bool("OCRLLM_CODEX_FAST_MODE")
        if codex_fast_mode is not None:
            updates.setdefault("codex_vision", {})["fast_mode"] = codex_fast_mode
        codex_parallel = _env_int("OCRLLM_CODEX_PARALLEL_REQUESTS")
        if codex_parallel is not None:
            updates.setdefault("codex_vision", {})["parallel_requests"] = max(1, codex_parallel)
        codex_stagger = _env_float("OCRLLM_CODEX_REQUEST_STAGGER_SECONDS")
        if codex_stagger is not None:
            updates.setdefault("codex_vision", {})["request_stagger_seconds"] = max(0.0, codex_stagger)
        codex_vision_batch = _env_int("OCRLLM_CODEX_VISION_BATCH_SIZE")
        if codex_vision_batch is not None:
            updates.setdefault("codex_vision", {})["vision_batch_size"] = max(1, codex_vision_batch)
        codex_video_batch = _env_int("OCRLLM_CODEX_VIDEO_FRAME_BATCH_SIZE")
        if codex_video_batch is not None:
            updates.setdefault("codex_vision", {})["video_frame_batch_size"] = max(1, codex_video_batch)
        google_enabled = _env_bool("OCRLLM_GOOGLE_MODE_ENABLED")
        if google_enabled is not None:
            updates.setdefault("google_api", {})["enabled"] = google_enabled
        google_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if google_key:
            updates.setdefault("google_api", {})["api_key"] = google_key
        google_vision = os.environ.get("OCRLLM_GOOGLE_VISION_MODEL")
        if google_vision:
            updates.setdefault("google_api", {})["vision_model"] = normalize_google_ocr_vision_model(google_vision)
        google_audio = os.environ.get("OCRLLM_GOOGLE_AUDIO_MODEL")
        if google_audio:
            updates.setdefault("google_api", {})["audio_model"] = google_audio
        google_text = os.environ.get("OCRLLM_GOOGLE_TEXT_MODEL")
        if google_text:
            updates.setdefault("google_api", {})["text_model"] = google_text
        google_parallel = _env_int("OCRLLM_GOOGLE_PARALLEL_REQUESTS")
        if google_parallel is not None:
            updates.setdefault("google_api", {})["parallel_requests"] = max(1, google_parallel)
        google_stagger = _env_float("OCRLLM_GOOGLE_REQUEST_STAGGER_SECONDS")
        if google_stagger is not None:
            updates.setdefault("google_api", {})["request_stagger_seconds"] = max(0.0, google_stagger)
        google_vision_batch = _env_int("OCRLLM_GOOGLE_VISION_BATCH_SIZE")
        if google_vision_batch is not None:
            updates.setdefault("google_api", {})["vision_batch_size"] = max(1, google_vision_batch)
        google_video_batch = _env_int("OCRLLM_GOOGLE_VIDEO_FRAME_BATCH_SIZE")
        if google_video_batch is not None:
            updates.setdefault("google_api", {})["video_frame_batch_size"] = max(1, google_video_batch)
        google_audio_chunk = _env_int("OCRLLM_GOOGLE_AUDIO_CHUNK_SECONDS")
        if google_audio_chunk is not None:
            updates.setdefault("google_api", {})["audio_chunk_seconds"] = max(1, google_audio_chunk)
        google_audio_overlap = _env_int("OCRLLM_GOOGLE_AUDIO_OVERLAP_SECONDS")
        if google_audio_overlap is not None:
            updates.setdefault("google_api", {})["audio_overlap_seconds"] = max(0, google_audio_overlap)
        social_long_parallel = _env_int("OCRLLM_SOCIAL_LONG_LLM_PARALLEL_REQUESTS")
        if social_long_parallel is not None:
            updates.setdefault("social", {})["long_video_llm_parallel_requests"] = max(1, social_long_parallel)
        social_long_stagger = _env_float("OCRLLM_SOCIAL_LONG_LLM_REQUEST_STAGGER_SECONDS")
        if social_long_stagger is not None:
            updates.setdefault("social", {})["long_video_llm_request_stagger_seconds"] = max(0.0, social_long_stagger)
        if updates.get("codex_vision", {}).get("enabled"):
            codex_model_value = normalize_codex_vision_model(
                updates["codex_vision"].get("model", cfg.codex_vision.model)
            )
            updates.setdefault("codex_vision", {})["model"] = codex_model_value
            updates.setdefault("models", {})["vision_model"] = codex_model_value
            codex_updates = updates.get("codex_vision", {})
            updates.setdefault("concurrency", {})["llm_parallel_requests"] = max(
                1,
                int(codex_updates.get("parallel_requests", cfg.codex_vision.parallel_requests)),
            )
            updates.setdefault("concurrency", {})["llm_request_stagger_seconds"] = max(
                0.0,
                float(codex_updates.get("request_stagger_seconds", cfg.codex_vision.request_stagger_seconds)),
            )
            updates.setdefault("processing", {})["batch_size"] = max(
                1,
                int(codex_updates.get("vision_batch_size", cfg.codex_vision.vision_batch_size)),
            )
            updates.setdefault("video", {})["batch_size"] = max(
                1,
                int(codex_updates.get("video_frame_batch_size", cfg.codex_vision.video_frame_batch_size)),
            )
        return cfg.with_updates(**updates) if updates else cfg

    def with_updates(self, **kwargs) -> AppConfig:
        """返回新的配置实例，只接受嵌套 section 更新。"""
        replacements: dict[str, Any] = {}
        for key, value in kwargs.items():
            if key not in _SECTION_NAMES:
                raise TypeError(f"with_updates 仅接受 section 名称，未知配置段: {key}")
            if isinstance(value, dict):
                replacements[key] = replace(getattr(self, key), **value)
            else:
                replacements[key] = value
        return replace(self, **replacements)


_SECTION_NAMES = {
    "api",
    "vision_api",
    "codex_vision",
    "google_api",
    "models",
    "processing",
    "concurrency",
    "paths",
    "video",
    "imaging",
    "social",
    "shot_detection",
}
