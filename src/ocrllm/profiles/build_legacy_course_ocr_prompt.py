"""Build the fixed course OCR prompt used by the legacy OCR workflow."""

from __future__ import annotations

from collections.abc import Sequence


COURSE_OCR_PROMPT_VERSION = "course.legacy.board.20260920"
_COURSE_OCR_PROMPT = """这是上课板书/课件截图（图片编号：{image_names}）。
这些图片可能来自黑板、白板或投影PPT，可能具有手写个人风格。
请你在保留数学公式（使用LaTeX格式）和表格结构（使用Markdown表格）的情况下，识别并输出Markdown文件。
要求：
- 不添加额外内容，不遗漏内容，不简并内容
- 每张图片之前必须有一行 HTML 注释作为帧标记，格式为 <!-- meta:frame id=图片名 -->，然后是正文内容
- 识别手写文字时尽量准确，对于不确定的字符请保留最可能的结果
- 数学公式使用 LaTeX：行内 $...$，独立 $$...$$
- 表格必须使用标准 Markdown 表格语法，禁止用 ``` 代码块包裹表格
- ``` 只允许用于原文中出现的真实代码片段
- 正文中使用的标题一律从 ## 开始，禁止出现 # 一级标题
不需要输出任何图片中没有出现的内容。"""


def build_legacy_course_ocr_prompt(image_names: Sequence[str] | None = None) -> str:
    """Return the fixed template, or render original filenames for one batch."""
    if image_names is None:
        return _COURSE_OCR_PROMPT
    return _COURSE_OCR_PROMPT.replace("{image_names}", ", ".join(image_names))
