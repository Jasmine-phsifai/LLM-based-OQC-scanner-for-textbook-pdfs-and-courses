"""Build one read-only `codex exec` argv and its recognition prompt."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

CODEX_CLI_FAST_SERVICE_TIER = "priority"

_DISABLED_CODEX_FEATURES = (
    "shell_tool",
    "browser_use",
    "browser_use_external",
    "computer_use",
    "apps",
    "multi_agent",
    "plugins",
    "tool_suggest",
    "hooks",
    "memories",
    "image_generation",
    "standalone_web_search",
    "web_search_request",
)


def build_codex_exec_prompt(user_prompt: str, image_count: int) -> str:
    """Wrap the caller prompt with the read-only subprocess contract."""
    return (
        "你是 OCRLLM 的本机 Codex 只读识图子进程。"
        "只根据附加图片完成识别，不调用工具，不读取项目文件，不编辑文件，不联网，不解释过程。"
        f"本次共有 {image_count} 张图片。"
        "按用户原始提示要求输出最终识别内容；如果原始提示要求 Markdown，就只输出 Markdown 正文。"
        "如果识别任务令人困惑或无法根据附加图片完成，请只回复 `SORRY4OCRLLM, because {原因}`，除此之外不要输出任何内容。\n\n"
        "用户原始提示:\n"
        f"{user_prompt}"
    )


def build_codex_exec_command(
    *,
    command: str,
    model: str,
    reasoning_effort: str,
    fast_mode: bool,
    image_paths: Sequence[Path],
    cwd: Path,
    output_path: Path,
    prompt: str,
) -> list[str]:
    """Assemble the non-interactive read-only exec invocation."""
    cmd = [
        command,
        "--ask-for-approval",
        "never",
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "-C",
        str(cwd),
        "--sandbox",
        "read-only",
        "-m",
        model,
        "-c",
        f'model_reasoning_effort="{reasoning_effort}"',
        "--output-last-message",
        str(output_path),
    ]
    if fast_mode:
        cmd.extend(["-c", f'service_tier="{CODEX_CLI_FAST_SERVICE_TIER}"'])
    for feature in _DISABLED_CODEX_FEATURES:
        cmd.extend(["--disable", feature])
    for path in image_paths:
        cmd.extend(["-i", str(Path(path).resolve())])
    cmd.append("--")
    cmd.append(prompt)
    return cmd
