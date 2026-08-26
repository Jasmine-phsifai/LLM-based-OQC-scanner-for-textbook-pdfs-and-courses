# imaging/ — 图像与音频底层处理

底层图像处理和 OCR 引擎封装。提供纯粹的图像/音频处理能力，不含业务逻辑。

## 文件说明

| 文件 | 说明 |
|------|------|
| `audio_extractor.py` | **音频提取** — 使用 ffmpeg 从视频文件提取音频并转码为 MP3。支持协作式取消。 |
| `ocr_engine.py` | **OCR 引擎** — RapidOCR (ONNX Runtime) 封装。纯 Python 进程内 OCR，无需外部可执行文件。支持图片文件和字节数据输入。 |
| `pdf_renderer.py` | **PDF 渲染器** — 基于 PyMuPDF (fitz) 的并行 PDF 页面渲染。按 DPI 渲染为 JPEG 图片，直接计算 zoom 避免后渲染 resize。 |
| `prepare_board_image.py` | **完整图片准备** — 保留完整画面；只在格式或尺寸需要时转换、等比例缩小，不做黑板定位、ROI 裁剪或透视矫正。 |
| `scan_detector.py` | **扫描检测** — 采样 PDF 页面文本量，判断是否为扫描版（文本量低于阈值）。帮助自动选择 OCR 模式或 LLM 公式识别模式。 |
| `tbpu.py` | **排版解析 (TBPU)** — 移植自 Umi-OCR 的 GapTree 间隙树排序算法。将 OCR 识别的散乱文本块按人类阅读顺序重排，支持多列版面。含段落分析器。 |

## 关键能力

- **无外部 OCR 进程**: RapidOCR 在 Python 进程内通过 ONNX Runtime 运行
- **并行渲染**: PDF 页面渲染使用线程池，0.4s/页
- **中文路径**: `imwrite_unicode` 解决 OpenCV 不支持中文路径的问题
- **GapTree 排序**: 支持多列、旋转文档的正确阅读顺序还原
