"""Build the fixed course OCR prompt used by the legacy OCR workflow."""

from __future__ import annotations

from collections.abc import Sequence


COURSE_OCR_PROMPT_VERSION = "course.legacy.v1"
_COURSE_OCR_PROMPT = """这是上课板书/课件截图（图片编号：{image_names}）。
这些图片可能来自黑板、白板或投影 PPT，可能具有手写个人风格。
请严格转写图片中的全部可见课程内容，并输出为结构清楚的 Markdown。

要求：
- 不添加额外内容，不遗漏内容，不简并内容，不讲解、不求解、不总结
- 每张图片之前必须有一行 HTML 注释作为帧标记，格式为 <!-- meta:frame id=图片名 -->，然后按阅读顺序输出该图片的正文和图形转写
- 识别手写文字时尽量准确；不确定的字符保留最可能结果，但不得据此虚构完整结论
- 数学公式使用 LaTeX：行内 $...$，独立 $$...$$
- 表格必须使用标准 Markdown 表格语法，禁止用代码块包裹表格
- 严禁输出 ```markdown 或 ```md
- 正文中使用的标题一律从 ## 开始，禁止出现 # 一级标题

图形与结构化视觉内容：
- 只有当代码比纯文字更能忠实保留图片中清晰可见的结构时，才生成下列代码；不要为了展示能力而强行生成。
- 流程图、关系图、状态转换图：使用 `mermaid` 代码块，保留可见节点文字、连接方向、分支和层级；不得补充图片中没有的节点或关系。
- 简单且结构清楚的函数图、统计图、几何图或示意图：使用 `svg` 代码块，输出一个完整、可独立渲染的 `<svg>`。保留可见的坐标轴、曲线、柱形、点、线、箭头、区域和文字标签；看不清的数值、函数、比例或几何约束不得猜测。SVG 禁止脚本、事件属性、动画、外部资源和 `foreignObject`。
- 清晰可辨的有机物结构：使用 `smiles` 代码块，以一行一个分子的 SMILES 表达可见的原子、键级、支链、环和明确标出的立体化学；不得根据模糊线条猜测原子、键级或手性。反应物与产物分开转写，不推断图片未写出的反应条件或产物。
- 对复杂彩图、医学影像、照片、自由手绘图，或任何无法可靠代码化的图，只转写可见标签并客观描述关键视觉关系，不强行输出 Mermaid、SVG 或 SMILES。
- Mermaid、SVG 和 SMILES 是对图片可见内容的等价转写，不是讲解、求解或扩写。除代码无法表达的可见信息外，不在代码块后追加分析。
- 代码围栏只允许用于原文中出现的真实代码片段，以及上述 `mermaid`、`svg`、`smiles` 图形转写；禁止用代码围栏包裹普通正文、标题、公式或 Markdown 表格。

只输出最终 Markdown，不要输出任何解释、说明或额外前后缀。"""


def build_legacy_course_ocr_prompt(image_names: Sequence[str] | None = None) -> str:
    """Return the fixed template, or render original filenames for one batch."""
    if image_names is None:
        return _COURSE_OCR_PROMPT
    return _COURSE_OCR_PROMPT.replace("{image_names}", ", ".join(image_names))
