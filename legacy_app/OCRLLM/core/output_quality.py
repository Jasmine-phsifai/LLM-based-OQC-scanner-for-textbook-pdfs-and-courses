"""Shared checks for generated Markdown outputs before marking tasks complete."""

from __future__ import annotations

import re


_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", flags=re.DOTALL)
_MARKDOWN_NOISE_RE = re.compile(r"[\s#>*_`~\-\[\](){}|:：,，.。;；!！?？/\\]+")
_FAILURE_MARKERS = ("识别失败", "OCR 失败")

# Model text refusals: the provider returned HTTP 200 with well-formed markdown
# structure (frame markers / page headers all present) but the body is the
# model declining to look at the image, not an actual recognition. This text
# is non-empty and contains no exception, so retry/empty-response detection
# never sees it; only content inspection catches it.
_REFUSAL_MARKERS = (
    "无法识别",
    "无法读取",
    "无法访问",
    "未能获取到该图片",
    "未能读取",
    "未收到可读取的图片",
    "没有可读取的图片",
    "没有可读取的有效图片",
    "请重新上传",
    "当前对话中没有",
    "当前对话里没有",
)


def looks_like_refusal(text: str) -> bool:
    """Return True when a provider response is a text refusal, not real content.

    A refusal is short (a real recognition of one or more pages/frames is
    expected to be far longer) and contains one of the known refusal phrases.
    """
    stripped = (text or "").strip()
    if not stripped:
        return False
    if visible_text_char_count(stripped) > 200:
        return False
    return any(marker in stripped for marker in _REFUSAL_MARKERS)



def visible_text_char_count(markdown: str) -> int:
    """Count user-visible content characters, excluding metadata and failure comments."""
    without_comments = _HTML_COMMENT_RE.sub("", markdown or "")
    compact = _MARKDOWN_NOISE_RE.sub("", without_comments)
    return len(compact)


def failed_placeholder_quality_reason(
    markdown: str,
    *,
    expected_units: int,
    unit_name: str,
    min_chars_per_unit: int = 60,
    min_total_chars: int = 400,
) -> str | None:
    """Return a reason when failure placeholders dominate a generated output."""
    if not any(marker in (markdown or "") for marker in _FAILURE_MARKERS + _REFUSAL_MARKERS):
        return None
    minimum = max(min_total_chars, max(1, expected_units) * min_chars_per_unit)
    visible_chars = visible_text_char_count(markdown)
    if visible_chars < minimum:
        return (
            f"包含识别失败占位，且有效正文过少: {visible_chars} 字，"
            f"{expected_units} {unit_name}最低期望 {minimum} 字"
        )
    return None
