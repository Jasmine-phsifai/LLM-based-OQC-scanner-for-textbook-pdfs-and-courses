"""Interpret `codex exec` output: refusals, attachment loss, diagnostics."""

from __future__ import annotations

import re

_REFUSAL_PREFIX = "sorry4ocrllm"

# The Codex backend intermittently drops -i attachments while still exiting 0;
# the model then reports it cannot see the attached images.
_IMAGE_ACCESS_REFUSAL_MARKERS = (
    "无法访问",
    "无法读取",
    "无法打开",
    "路径不存在",
    "cannot access",
    "cannot read",
    "cannot open",
    "unable to access",
    "unable to read",
    "not able to access",
    "no attached image",
    "not attached",
)


def parse_codex_refusal(text: str) -> str | None:
    """Return the SORRY4OCRLLM refusal reason, or None for real content."""
    stripped = (text or "").strip()
    if not stripped.casefold().startswith(_REFUSAL_PREFIX):
        return None
    because_match = re.search(r"\bbecause\b", stripped, flags=re.IGNORECASE)
    if because_match:
        reason = stripped[because_match.end():]
    else:
        reason = stripped[len(_REFUSAL_PREFIX):]
    return reason.strip(" \t\r\n,，.:：;；!?！？-—") or "未提供原因"


def is_image_access_refusal(reason: str) -> bool:
    """Classify a refusal as transient server-side attachment loss."""
    lowered = (reason or "").casefold()
    return any(marker in lowered for marker in _IMAGE_ACCESS_REFUSAL_MARKERS)


def summarize_codex_failure_output(output: str, returncode: int) -> str:
    """Keep CLI diagnostics useful without dumping prompts into error details."""
    lines = [line.strip() for line in (output or "").splitlines() if line.strip()]
    if not lines:
        return f"Codex CLI exited with code {returncode} without diagnostic output"

    session_id = ""
    for line in lines:
        if line.lower().startswith("session id:"):
            session_id = line.split(":", 1)[1].strip()
            break

    prompt_markers = (
        "user",
        "用户原始提示",
        "你是 OCRLLM",
        "这是上课板书",
        "<!-- meta:",
    )
    diagnostic_keywords = (
        "error",
        "failed",
        "failure",
        "timeout",
        "timed out",
        "quota",
        "rate limit",
        "429",
        "500",
        "401",
        "403",
        "connection",
        "refused",
        "denied",
        "invalid",
        "reading additional input",
    )

    diagnostic_lines = []
    for line in lines:
        lower = line.lower()
        if any(marker in line for marker in prompt_markers):
            continue
        if any(keyword in lower for keyword in diagnostic_keywords):
            diagnostic_lines.append(line)

    if diagnostic_lines:
        primary = diagnostic_lines[-1]
    else:
        primary = next(
            (line for line in lines if not any(marker in line for marker in prompt_markers)),
            lines[0],
        )

    detail = f"Codex CLI exited with code {returncode}: {primary}"
    if session_id:
        detail += f"; session id: {session_id}"
    return _single_line(detail)


def _single_line(text: str, limit: int = 500) -> str:
    detail = " ".join((text or "").split())
    if len(detail) > limit:
        detail = detail[:limit].rstrip() + "..."
    return detail
