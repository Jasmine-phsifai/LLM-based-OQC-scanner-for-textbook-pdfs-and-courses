"""本机 Codex CLI 视觉识别适配层。"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from OCRLLM.config import (
    AppConfig,
    CodexVisionConfig,
    CODEX_VISION_RUNTIME_BATCH_SIZE,
    CODEX_VISION_RUNTIME_PARALLEL,
    CODEX_VISION_RUNTIME_STAGGER_SECONDS,
    CODEX_VISION_RUNTIME_VIDEO_BATCH_SIZE,
    DEFAULT_CODEX_VISION_REASONING_EFFORT,
)
from OCRLLM.core.codex_model_catalog import (
    CODEX_VISION_DEFAULT_MODEL,
    CODEX_VISION_MODEL_CHOICES,
    migrate_stored_codex_vision_model,
    normalize_codex_vision_model,
)
from OCRLLM.core.utils import windows_no_window_kwargs

logger = logging.getLogger(__name__)

CODEX_VISION_DEFAULT_REASONING = DEFAULT_CODEX_VISION_REASONING_EFFORT
CODEX_VISION_BATCH_SIZE = CODEX_VISION_RUNTIME_BATCH_SIZE
CODEX_VISION_MAX_PARALLEL = CODEX_VISION_RUNTIME_PARALLEL
CODEX_VISION_STAGGER_SECONDS = CODEX_VISION_RUNTIME_STAGGER_SECONDS
CODEX_VISION_VIDEO_BATCH_SIZE = CODEX_VISION_RUNTIME_VIDEO_BATCH_SIZE
CODEX_VISION_REASONING_LEVELS = ("low", "medium", "high", "xhigh")

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

_REQUIRED_ROOT_FLAGS = (
    "--ask-for-approval",
)

_REQUIRED_EXEC_FLAGS = (
    "--image",
    "--model",
    "--sandbox",
    "--disable",
    "--ephemeral",
    "--ignore-user-config",
    "--ignore-rules",
    "--output-last-message",
)

_CODEX_VISION_MAX_ATTEMPTS = 2
_CODEX_VISION_RETRY_DELAY_SECONDS = 3.0


class CodexCLIUnavailableError(RuntimeError):
    """Codex CLI 不可用或不满足本机识图要求。"""


@dataclass(frozen=True)
class CodexInspectionReport:
    ok: bool
    message: str
    version: str = ""


def _run_codex_process(
    cmd: list[str],
    *,
    timeout: float,
    stdin=None,
):
    """Run Codex CLI with UTF-8 output decoding across Windows and Linux."""
    kwargs = {
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "capture_output": True,
        "stdin": stdin,
        "timeout": timeout,
        "check": False,
    }
    kwargs.update(windows_no_window_kwargs())
    return subprocess.run(cmd, **kwargs)


def _run_probe(cmd: list[str], timeout: float = 20.0):
    return _run_codex_process(cmd, timeout=timeout)


def _codex_launch_failure_message(prefix: str, command: str, exc: BaseException) -> str:
    message = f"{prefix}: {exc}"
    resolved = shutil.which(command) or command
    if os.name == "nt" and "WindowsApps" in str(resolved) and "OpenAI.Codex_" in str(resolved):
        message += (
            "；当前 PATH 命中 WindowsApps 中的 Codex Desktop 内部入口，普通 Python 进程无权执行。"
            "请安装可独立调用的 Codex CLI，或在设置里填写该 CLI 的完整命令/路径。"
        )
    return message


def _single_line_detail(text: str, limit: int = 500) -> str:
    detail = " ".join((text or "").split())
    if len(detail) > limit:
        detail = detail[:limit].rstrip() + "..."
    return detail


def _summarize_codex_failure_output(output: str, returncode: int) -> str:
    """Keep Codex CLI diagnostics useful without dumping prompts into output MD."""
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
    return _single_line_detail(detail)


def inspect_codex_cli(cfg: CodexVisionConfig) -> CodexInspectionReport:
    """检测 Codex CLI 是否支持当前识图配置。"""
    command = (cfg.command or "codex").strip()
    if not shutil.which(command):
        return CodexInspectionReport(False, f"未找到 Codex 命令: {command}")

    try:
        version_result = _run_probe([command, "--version"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CodexInspectionReport(False, _codex_launch_failure_message("Codex 版本检测失败", command, exc))
    version = (version_result.stdout or version_result.stderr or "").strip()
    if version_result.returncode != 0:
        return CodexInspectionReport(False, f"Codex 版本检测失败: {version}", version)
    try:
        root_help_result = _run_probe([command, "--help"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CodexInspectionReport(False, _codex_launch_failure_message("Codex 全局参数检测失败", command, exc), version)
    root_help_text = f"{root_help_result.stdout}\n{root_help_result.stderr}"
    missing_root_flags = [flag for flag in _REQUIRED_ROOT_FLAGS if flag not in root_help_text]
    if missing_root_flags:
        return CodexInspectionReport(
            False,
            "当前 Codex 缺少必要全局参数: " + ", ".join(missing_root_flags),
            version,
        )

    try:
        help_result = _run_probe([command, "exec", "--help"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CodexInspectionReport(False, _codex_launch_failure_message("Codex exec 功能检测失败", command, exc), version)
    help_text = f"{help_result.stdout}\n{help_result.stderr}"
    if help_result.returncode != 0:
        return CodexInspectionReport(False, "当前 Codex 不支持非交互 exec 调用", version)
    missing_flags = [flag for flag in _REQUIRED_EXEC_FLAGS if flag not in help_text]
    if missing_flags:
        return CodexInspectionReport(
            False,
            "当前 Codex exec 缺少必要参数: " + ", ".join(missing_flags),
            version,
        )

    try:
        models_result = _run_probe([command, "debug", "models"], timeout=30.0)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CodexInspectionReport(False, _codex_launch_failure_message("Codex 模型目录检测失败", command, exc), version)
    if models_result.returncode != 0:
        detail = (models_result.stderr or models_result.stdout or "").strip()
        return CodexInspectionReport(False, f"Codex 模型目录检测失败: {detail}", version)

    model_name = normalize_codex_vision_model(cfg.model)
    try:
        raw = json.loads(models_result.stdout or "{}")
    except json.JSONDecodeError as exc:
        return CodexInspectionReport(False, f"Codex 模型目录不是有效 JSON: {exc}", version)
    models = raw.get("models") or []
    image_model_slugs = [
        item.get("slug")
        for item in models
        if "image" in set(item.get("input_modalities") or []) and item.get("slug")
    ]
    suggestion = f"；可选图片模型: {', '.join(image_model_slugs[:5])}" if image_model_slugs else ""
    model = next((item for item in models if item.get("slug") == model_name), None)
    if not model:
        return CodexInspectionReport(False, f"Codex 模型不可用: {model_name}{suggestion}", version)
    modalities = set(model.get("input_modalities") or [])
    if "image" not in modalities:
        return CodexInspectionReport(False, f"Codex 模型不支持图片输入: {model_name}{suggestion}", version)
    supported_efforts = {
        item.get("effort")
        for item in (model.get("supported_reasoning_levels") or [])
        if item.get("effort")
    }
    effort = (cfg.reasoning_effort or CODEX_VISION_DEFAULT_REASONING).strip()
    if supported_efforts and effort not in supported_efforts:
        return CodexInspectionReport(False, f"模型 {model_name} 不支持思考强度: {effort}", version)

    return CodexInspectionReport(True, f"Codex 可用: {version or command}, model={model_name}, reasoning={effort}", version)


def apply_codex_vision_runtime_limits(cfg: AppConfig) -> AppConfig:
    """Apply Codex-specific runtime controls to the legacy processor fields."""
    if not cfg.codex_vision.enabled:
        return cfg
    model = normalize_codex_vision_model(cfg.codex_vision.model)
    return cfg.with_updates(
        codex_vision={"model": model},
        models={"vision_model": model},
        concurrency={
            "llm_parallel_requests": max(1, int(cfg.codex_vision.parallel_requests)),
            "llm_request_stagger_seconds": max(0.0, float(cfg.codex_vision.request_stagger_seconds)),
        },
        processing={"batch_size": max(1, int(cfg.codex_vision.vision_batch_size))},
        video={"batch_size": max(1, int(cfg.codex_vision.video_frame_batch_size))},
    )


class CodexVisionRunner:
    """通过 `codex exec` 进行只读图片识别。"""

    def __init__(self, cfg: CodexVisionConfig):
        self.cfg = cfg

    def recognize(self, prompt: str, image_paths: list[str]) -> str:
        batch_limit = max(
            1,
            int(self.cfg.vision_batch_size),
            int(self.cfg.video_frame_batch_size),
        )
        if len(image_paths) > batch_limit:
            raise CodexCLIUnavailableError(
                f"Codex 模式单次最多识别 {batch_limit} 张图片，当前 {len(image_paths)} 张"
            )
        if not image_paths:
            raise CodexCLIUnavailableError("Codex 模式需要至少一张图片")
        command = (self.cfg.command or "codex").strip()
        if not shutil.which(command):
            raise CodexCLIUnavailableError(f"未找到 Codex 命令: {command}")
        missing = [path for path in image_paths if not Path(path).exists()]
        if missing:
            raise CodexCLIUnavailableError(f"图片不存在: {missing[0]}")

        with tempfile.TemporaryDirectory(prefix="ocrllm_codex_") as tmp:
            output_path = Path(tmp) / "last_message.txt"
            cmd = self._build_command(
                command=command,
                prompt=self._build_prompt(prompt, len(image_paths)),
                image_paths=image_paths,
                cwd=tmp,
                output_path=str(output_path),
            )
            logger.info(
                "[CODEX] 本机 Codex 识图: model=%s, 图片=%d",
                normalize_codex_vision_model(self.cfg.model),
                len(image_paths),
            )
            timeout_seconds = max(30, int(self.cfg.timeout_seconds or 1800))
            for attempt in range(1, _CODEX_VISION_MAX_ATTEMPTS + 1):
                if output_path.exists():
                    output_path.unlink()
                try:
                    result = _run_codex_process(
                        cmd,
                        stdin=subprocess.DEVNULL,
                        timeout=timeout_seconds,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise CodexCLIUnavailableError(f"Codex 识图超时: {exc}") from exc
                except OSError as exc:
                    raise CodexCLIUnavailableError(_codex_launch_failure_message("Codex 识图启动失败", command, exc)) from exc

                if result.returncode != 0:
                    detail = _summarize_codex_failure_output(
                        result.stderr or result.stdout or "",
                        result.returncode,
                    )
                    if attempt < _CODEX_VISION_MAX_ATTEMPTS:
                        logger.warning(
                            "[CODEX] 识图失败，将重试 %d/%d: %s",
                            attempt + 1,
                            _CODEX_VISION_MAX_ATTEMPTS,
                            detail,
                        )
                        time.sleep(_CODEX_VISION_RETRY_DELAY_SECONDS * attempt)
                        continue
                    raise CodexCLIUnavailableError(f"Codex 识图失败: {detail}")

                text = output_path.read_text(encoding="utf-8").strip() if output_path.exists() else ""
                if not text:
                    text = (result.stdout or "").strip()
                if text:
                    stripped_text = text.strip()
                    if stripped_text.casefold().startswith("sorry4ocrllm"):
                        because_match = re.search(r"\bbecause\b", stripped_text, flags=re.IGNORECASE)
                        if because_match:
                            reason = stripped_text[because_match.end():]
                        else:
                            reason = stripped_text[len("SORRY4OCRLLM"):]
                        reason = reason.strip(" \t\r\n,，.:：;；!?！？-—") or "未提供原因"
                        if attempt < _CODEX_VISION_MAX_ATTEMPTS:
                            logger.warning(
                                "[CODEX] 识图被拒绝，将重试 %d/%d: %s",
                                attempt + 1,
                                _CODEX_VISION_MAX_ATTEMPTS,
                                reason,
                            )
                            time.sleep(_CODEX_VISION_RETRY_DELAY_SECONDS * attempt)
                            continue
                        raise CodexCLIUnavailableError(f"Codex 拒绝识别: {reason}")
                    return text

                if attempt < _CODEX_VISION_MAX_ATTEMPTS:
                    logger.warning(
                        "[CODEX] 识图返回空内容，将重试 %d/%d",
                        attempt + 1,
                        _CODEX_VISION_MAX_ATTEMPTS,
                    )
                    time.sleep(_CODEX_VISION_RETRY_DELAY_SECONDS * attempt)
                    continue
                raise CodexCLIUnavailableError("Codex 识图返回空内容")

            raise CodexCLIUnavailableError("Codex 识图失败")

    def _build_command(
        self,
        *,
        command: str,
        prompt: str,
        image_paths: Iterable[str],
        cwd: str,
        output_path: str,
    ) -> list[str]:
        model = normalize_codex_vision_model(self.cfg.model)
        effort = (self.cfg.reasoning_effort or CODEX_VISION_DEFAULT_REASONING).strip()
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
            cwd,
            "--sandbox",
            "read-only",
            "-m",
            model,
            "-c",
            f'model_reasoning_effort="{effort}"',
            "--output-last-message",
            output_path,
        ]
        for feature in _DISABLED_CODEX_FEATURES:
            cmd.extend(["--disable", feature])
        for path in image_paths:
            cmd.extend(["-i", str(Path(path).resolve())])
        cmd.append("--")
        cmd.append(prompt)
        return cmd

    @staticmethod
    def _build_prompt(user_prompt: str, image_count: int) -> str:
        return (
            "你是 OCRLLM 的本机 Codex 只读识图子进程。"
            "只根据附加图片完成识别，不调用工具，不读取项目文件，不编辑文件，不联网，不解释过程。"
            f"本次共有 {image_count} 张图片。"
            "按用户原始提示要求输出最终识别内容；如果原始提示要求 Markdown，就只输出 Markdown 正文。"
            "如果识别任务令人困惑或无法根据附加图片完成，请只回复 `SORRY4OCRLLM, because {原因}`，除此之外不要输出任何内容。\n\n"
            "用户原始提示:\n"
            f"{user_prompt}"
        )
