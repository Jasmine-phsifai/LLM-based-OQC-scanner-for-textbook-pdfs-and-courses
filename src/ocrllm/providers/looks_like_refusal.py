"""Detect provider responses that decline the task instead of recognizing it."""

from __future__ import annotations

import re
import unicodedata


# A refusal arrives as ordinary assistant content with HTTP 200 and passes every
# structural check, so only phrase inspection can separate it from a short
# transcription. Length caps the false-positive risk: a real board recognition
# that happens to contain one of these phrases is far longer than the cap.
_MAXIMUM_REFUSAL_VISIBLE_CHARACTERS = 300

_REFUSAL_MARKERS = (
    "无法识别",
    "无法读取",
    "无法访问",
    "无法查看",
    "无法处理",
    "未能获取到该图片",
    "未能读取",
    "未收到可读取的图片",
    "没有可读取的图片",
    "没有可读取的有效图片",
    "请重新上传",
    "请提供图片",
    "当前对话中没有",
    "当前对话里没有",
    "i'm sorry",
    "i am sorry",
    "i'm unable",
    "i am unable",
    "i cannot",
    "i can't",
    "i can not",
    "unable to identify",
    "unable to read",
    "unable to process",
    "cannot assist",
    "can't assist",
    "no image was provided",
    "there is no image",
    "as an ai",
)

_MARKDOWN_NOISE = re.compile(r"<!--.*?-->", flags=re.DOTALL)


def looks_like_refusal(markdown: str) -> bool:
    """Return True when a short response is the model declining, not content."""
    stripped = markdown.strip()
    if not stripped:
        return False
    if _visible_character_count(stripped) > _MAXIMUM_REFUSAL_VISIBLE_CHARACTERS:
        return False
    folded = stripped.casefold()
    return any(marker in folded for marker in _REFUSAL_MARKERS)


def _visible_character_count(markdown: str) -> int:
    without_comments = _MARKDOWN_NOISE.sub("", markdown)
    return sum(
        1
        for character in without_comments
        if unicodedata.category(character)[0] in {"L", "N"}
    )
