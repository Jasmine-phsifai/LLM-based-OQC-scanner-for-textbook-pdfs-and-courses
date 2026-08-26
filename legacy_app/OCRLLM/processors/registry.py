"""处理器注册表。"""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib
import threading
from pathlib import Path
from typing import Any

from OCRLLM.core.document_model import SourceType


@dataclass(frozen=True, slots=True)
class ProcessorSpec:
    """处理器元数据规格（冻结数据类）。"""
    key: str
    display_name: str
    module_path: str
    class_name: str
    supported_extensions: tuple[str, ...]
    source_type: SourceType
    input_kind: str
    accepts_multiple_files: bool = False
    supports_resume: bool = False
    experimental: bool = False
    description: str = ""
    output_target: str = "file"
    cli_input_help: str = "输入文件路径"
    cli_output_help: str = "输出路径"
    cli_option_groups: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def source_kind(self) -> str:
        """兼容旧字段名；新代码应使用 input_kind。"""
        return self.input_kind

    def matches_path(self, path: str) -> bool:
        """判断文件路径是否匹配该处理器支持的扩展名。

        Args:
            path: 文件路径。

        Returns:
            是否匹配。
        """
        return Path(path).suffix.lower() in self.supported_extensions

    def load_processor_class(self):
        """动态导入并返回该处理器的类对象。

        Returns:
            处理器类。
        """
        module = importlib.import_module(self.module_path)
        processor_cls = getattr(module, self.class_name)
        class_source_type = getattr(processor_cls, "source_type", SourceType.UNKNOWN)
        if class_source_type != self.source_type:
            raise ValueError(
                f"处理器元数据不一致: registry[{self.key}].source_type={self.source_type.value!r}, "
                f"{self.class_name}.source_type={getattr(class_source_type, 'value', class_source_type)!r}"
            )
        return processor_cls


class ProcessorRegistry:
    """处理器注册中心 — 管理所有可用处理器的注册和查询。"""
    def __init__(self):
        self._specs: dict[str, ProcessorSpec] = {}

    def register(self, spec: ProcessorSpec):
        """注册一个处理器规格。

        Args:
            spec: 处理器元数据。

        Raises:
            ValueError: 同名处理器已注册。
        """
        if spec.key in self._specs:
            raise ValueError(f"processor already registered: {spec.key}")
        self._specs[spec.key] = spec

    def get(self, key: str) -> ProcessorSpec:
        """按 key 查找处理器规格。

        Args:
            key: 处理器标识（如 ``pdf``、``video``）。

        Returns:
            ProcessorSpec 实例。

        Raises:
            KeyError: 未找到。
        """
        try:
            return self._specs[key]
        except KeyError as exc:
            raise KeyError(f"unknown processor: {key}") from exc

    def all(self) -> list[ProcessorSpec]:
        """返回所有已注册的处理器规格列表。"""
        return list(self._specs.values())

    def for_path(self, path: str) -> ProcessorSpec:
        """根据文件路径后缀匹配处理器。

        Args:
            path: 文件路径。

        Returns:
            匹配的 ProcessorSpec。

        Raises:
            KeyError: 无匹配处理器。
        """
        suffix = Path(path).suffix.lower()
        for spec in self._specs.values():
            if suffix in spec.supported_extensions:
                return spec
        raise KeyError(f"no processor registered for suffix: {suffix or '<none>'}")

    def create(self, key: str, **kwargs):
        """按 key 创建处理器实例。

        Args:
            key: 处理器标识。
            **kwargs: 传递给处理器构造函数的参数。

        Returns:
            处理器实例。
        """
        return self.get(key).load_processor_class()(**kwargs)

    def create_for_path(self, path: str, **kwargs):
        """根据文件路径自动匹配并创建处理器实例。

        Args:
            path: 文件路径。
            **kwargs: 传递给处理器构造函数的参数。

        Returns:
            处理器实例。
        """
        return self.for_path(path).load_processor_class()(**kwargs)


def _builtin_specs() -> list[ProcessorSpec]:
    return [
        ProcessorSpec(
            key="pdf",
            display_name="PDF 识别",
            module_path="OCRLLM.processors.pdf",
            class_name="PDFProcessor",
            supported_extensions=(".pdf",),
            source_type=SourceType.PDF,
            input_kind="document",
            supports_resume=True,
            description="PDF 课本/课件识别为 Markdown。",
            cli_input_help="PDF 文件路径",
            cli_output_help="输出 MD 路径",
            cli_option_groups=("formula", "page_range"),
        ),
        ProcessorSpec(
            key="board",
            display_name="板书/截图识别",
            module_path="OCRLLM.processors.board",
            class_name="BoardProcessor",
            supported_extensions=(".jpg", ".jpeg", ".png", ".bmp", ".webp", ".heic", ".heif", ".tif", ".tiff"),
            source_type=SourceType.BOARD,
            input_kind="image",
            accepts_multiple_files=True,
            description="单张或多张板书/截图识别。",
            cli_input_help="图片文件路径",
            cli_output_help="输出 MD 路径",
            cli_option_groups=(),
        ),
        ProcessorSpec(
            key="video",
            display_name="录课视频识别",
            module_path="OCRLLM.processors.video",
            class_name="VideoProcessor",
            supported_extensions=(".mp4", ".avi", ".mkv", ".mov", ".flv", ".wmv"),
            source_type=SourceType.VIDEO,
            input_kind="video",
            supports_resume=True,
            description="录课视频抽帧、板书识别与语音识别。",
            output_target="directory",
            cli_input_help="视频文件路径",
            cli_output_help="输出目录",
            cli_option_groups=("phases", "resume"),
        ),
        ProcessorSpec(
            key="audio",
            display_name="语音识别",
            module_path="OCRLLM.processors.audio",
            class_name="AudioProcessor",
            supported_extensions=(".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"),
            source_type=SourceType.AUDIO,
            input_kind="audio",
            description="音频文件转写为 Markdown。",
            cli_input_help="音频文件路径",
            cli_output_help="输出 MD 路径",
            cli_option_groups=("hotwords",),
        ),
        ProcessorSpec(
            key="pptx",
            display_name="PPTX 课件",
            module_path="OCRLLM.processors.future_formats",
            class_name="PPTXProcessor",
            supported_extensions=(".pptx",),
            source_type=SourceType.PPTX,
            input_kind="document",
            description="PPTX 课件文本提取为 Markdown。",
            cli_input_help="PPTX 文件路径",
            cli_output_help="输出 MD 路径",
        ),
        ProcessorSpec(
            key="ppt",
            display_name="PPT 课件",
            module_path="OCRLLM.processors.future_formats",
            class_name="PPTProcessor",
            supported_extensions=(".ppt",),
            source_type=SourceType.PPT,
            input_kind="document",
            description="PPT 课件文本提取为 Markdown。",
            cli_input_help="PPT 文件路径",
            cli_output_help="输出 MD 路径",
        ),
        ProcessorSpec(
            key="docx",
            display_name="DOCX 文档",
            module_path="OCRLLM.processors.future_formats",
            class_name="DOCXProcessor",
            supported_extensions=(".docx",),
            source_type=SourceType.DOCX,
            input_kind="document",
            description="DOCX 文档文本提取为 Markdown。",
            cli_input_help="DOCX 文件路径",
            cli_output_help="输出 MD 路径",
        ),
        ProcessorSpec(
            key="doc",
            display_name="DOC 文档",
            module_path="OCRLLM.processors.future_formats",
            class_name="DOCProcessor",
            supported_extensions=(".doc",),
            source_type=SourceType.DOC,
            input_kind="document",
            description="DOC 文档文本提取为 Markdown。",
            cli_input_help="DOC 文件路径",
            cli_output_help="输出 MD 路径",
        ),
        ProcessorSpec(
            key="html",
            display_name="HTML 课件",
            module_path="OCRLLM.processors.future_formats",
            class_name="HTMLProcessor",
            supported_extensions=(".html", ".htm"),
            source_type=SourceType.HTML,
            input_kind="document",
            experimental=True,
            description="HTML 课程页面解析占位处理器。",
            cli_input_help="HTML 文件路径",
            cli_output_help="输出 MD 路径",
        ),
        ProcessorSpec(
            key="social_long",
            display_name="社交媒体长视频识别",
            module_path="OCRLLM.processors.social.long_video",
            class_name="SocialLongVideoProcessor",
            supported_extensions=(),
            source_type=SourceType.SOCIAL_VIDEO,
            input_kind="url",
            supports_resume=True,
            description="B站/YouTube 长视频课程下载+识别（复用录课 Pipeline）。",
            output_target="directory",
            cli_input_help="视频页面 URL",
            cli_output_help="输出目录",
            cli_option_groups=("phases", "resume", "parts"),
        ),
        ProcessorSpec(
            key="social_short",
            display_name="短视频知识识别",
            module_path="OCRLLM.processors.social.short_video",
            class_name="ShortVideoProcessor",
            supported_extensions=(),
            source_type=SourceType.SOCIAL_VIDEO,
            input_kind="url",
            supports_resume=False,
            description="社交媒体短视频场景切换检测+LLM 画面描述+ASR。",
            output_target="directory",
            cli_input_help="视频页面 URL",
            cli_output_help="输出目录",
        ),
    ]


_DEFAULT_REGISTRY: ProcessorRegistry | None = None
_REGISTRY_LOCK = threading.Lock()


def get_default_registry() -> ProcessorRegistry:
    """获取全局默认处理器注册表（延迟初始化、线程安全）。

    Returns:
        ProcessorRegistry 实例。
    """
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is not None:
        return _DEFAULT_REGISTRY
    with _REGISTRY_LOCK:
        if _DEFAULT_REGISTRY is None:
            registry = ProcessorRegistry()
            for spec in _builtin_specs():
                registry.register(spec)
            _DEFAULT_REGISTRY = registry
    return _DEFAULT_REGISTRY


def get_processor_spec(key: str) -> ProcessorSpec:
    """按 key 查找全局注册表中的处理器规格。

    Args:
        key: 处理器标识。

    Returns:
        ProcessorSpec 实例。
    """
    return get_default_registry().get(key)


def get_processor_spec_for_path(path: str) -> ProcessorSpec:
    """根据文件路径查找处理器规格。

    Args:
        path: 文件路径。

    Returns:
        ProcessorSpec 实例。
    """
    return get_default_registry().for_path(path)


def create_processor(key: str, **kwargs):
    """按 key 从全局注册表创建处理器实例。

    Args:
        key: 处理器标识。
        **kwargs: 处理器构造参数。

    Returns:
        处理器实例。
    """
    return get_default_registry().create(key, **kwargs)


def create_processor_for_path(path: str, **kwargs):
    """根据文件路径从全局注册表自动创建处理器实例。

    Args:
        path: 文件路径。
        **kwargs: 处理器构造参数。

    Returns:
        处理器实例。
    """
    return get_default_registry().create_for_path(path, **kwargs)
