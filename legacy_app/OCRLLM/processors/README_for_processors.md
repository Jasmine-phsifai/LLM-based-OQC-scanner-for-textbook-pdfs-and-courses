# processors/ — 处理器层（业务逻辑）

各文件类型的核心处理逻辑。每个处理器继承 `BaseProcessor`，实现 `process()` 方法。

## 文件说明

| 文件 | 说明 |
|------|------|
| `base.py` | **处理器基类** — 依赖注入 (config, LLM, reporter, tracker, API pool)、进度报告、协作取消、并发 Future 迭代等通用逻辑。 |
| `pdf.py` | **PDF 处理器** — 两种模式: (1) OCR 模式: RapidOCR + GapTree 排版; (2) 公式模式: LLM 多模态识别，支持断点续传和增量写入。 |
| `board.py` | **板书处理器** — 多图上下文连续识别。完整图片准备 → 分批 → LLM 多模态请求（保留对话历史提升连贯性）→ 合并 Markdown。 |
| `video.py` | **视频处理器** — 5 阶段管线: 音频提取 → 智能抽帧 (变化检测 + pHash) → 完整帧等比例缩放 → LLM 板书识别 → ASR 语音识别。内置复杂的帧变化检测算法，不做黑板定位、ROI 裁剪或透视矫正。 |
| `video_pipeline.py` | **视频阶段管线框架** — `VideoPhase` 基类定义阶段生命周期 (should_run / can_resume / on_resume / execute)，`VideoProcessContext` 传递阶段间数据。 |
| `audio.py` | **语音处理器** — 自动选择短音频直接 ASR 或长音频异步任务。支持热词、分段并行识别、SSL 重试。 |
| `future_formats.py` | **扩展格式处理器** — DOCX/PPTX/DOC/PPT/HTML 处理器。DOCX/PPTX 通过 XML 解析提取文本，DOC/PPT 通过 OLE2 二进制解析。不需要 API Key。 |
| `registry.py` | **处理器注册表** — `ProcessorSpec` 声明处理器元数据，`ProcessorRegistry` 管理注册/查询/动态导入。内置 9 种格式的注册。 |
| `routing.py` | **输入路由** — 根据文件扩展名自动识别类型并匹配处理器。支持单文件和多文件（仅限同类图片）。 |

## 处理器注册与路由

```python
# 自动识别文件类型
from OCRLLM.processors.routing import route_input_paths
routed = route_input_paths(["lecture.mp4"])
print(routed.spec.key)  # "video"

# 按 key 创建处理器
from OCRLLM.processors.registry import create_processor
proc = create_processor("pdf", cfg=cfg, reporter=reporter)
result = proc.process(pdf_path="book.pdf", need_formula=True)
```

## 视频管线阶段

| 阶段 | 类 | 说明 |
|:---:|------|------|
| 1 | `AudioExtractPhase` | ffmpeg 提取音频 |
| 2 | `FrameExtractPhase` | 智能抽帧（变化检测 + pHash 去重） |
| 3 | `FrameResizePhase` | 完整帧等比例缩放（不裁剪） |
| 4 | `BoardRecognizePhase` | LLM 视觉识别 |
| 5 | `AudioRecognizePhase` | 语音识别 |

每个阶段支持断点续传: `can_resume()` 检查产物是否存在 → `on_resume()` 加载已有内容。
