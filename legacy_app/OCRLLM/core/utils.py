"""
公共工具函数 — 无状态纯函数，可被任何模块安全调用。
"""

import os
import re
import logging
import shutil
import subprocess
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

_PERSISTENT_LOG_MARKER = "_ocrllm_persistent_log"


_WINDOWS_RESERVED_TRAILING = re.compile(r"[ .]+$")


def sanitize_path_component(name: str, fallback: str = "_") -> str:
    """清理单个路径分量，避免 Windows 静默拒绝目录创建。

    Windows 会在解析路径时丢弃分量末尾的空格/句点（但 ``CreateDirectory``
    等 API 并不总是接受同样丢弃后的名字），导致 ``os.makedirs`` 抛出
    ``The system cannot find the path specified``。真正来源往往是原始
    文件名本身带有尾随空格（例如 "数理统计 .pdf"），而不是路径过长。

    Args:
        name: 原始目录/文件名分量（不含路径分隔符）。
        fallback: 清理后为空字符串时使用的占位名。

    Returns:
        去除首尾空格/句点后可安全用作 Windows 路径分量的名字。
    """
    cleaned = _WINDOWS_RESERVED_TRAILING.sub("", name.strip())
    return cleaned or fallback


def long_path(path: str) -> str:
    """在 Windows 上为超长绝对路径加上 ``\\\\?\\`` 前缀以绕过 260 字符限制。

    不做任何其他平台或相对路径的转换；调用方需自行保证传入的是绝对路径。
    """
    if sys.platform != "win32":
        return path
    normalized = os.path.abspath(path)
    if normalized.startswith("\\\\?\\") or len(normalized) < 240:
        return normalized
    if normalized.startswith("\\\\"):
        return "\\\\?\\UNC\\" + normalized.lstrip("\\")
    return "\\\\?\\" + normalized


def ensure_dir(path: str) -> str:
    """确保目录存在，不存在则创建。

    Args:
        path: 目录路径。

    Returns:
        规范化后的目录路径。
    """
    normalized = path or "."
    try:
        os.makedirs(normalized, exist_ok=True)
    except OSError:
        os.makedirs(long_path(normalized), exist_ok=True)
    return normalized


def resolve_workers(configured: int, task_count: int, hard_cap: int = 8) -> int:
    """根据配置和任务数智能计算工作线程数。

    Args:
        configured: 用户配置的线程数，0 表示自动。
        task_count: 任务数量。
        hard_cap: 上限。

    Returns:
        实际使用的线程数。
    """
    if task_count <= 1:
        return 1
    if configured and configured > 0:
        return max(1, min(configured, task_count))
    cpu = os.cpu_count() or 4
    return max(1, min(cpu, task_count, hard_cap))


def atomic_temp_path(dest: str) -> str:
    """同目录下的临时写入路径，扩展名保持在最后。

    PIL 和 PyMuPDF 都靠扩展名推断输出格式，把 ``.tmp1234`` 放在末尾会让写入直接报错。
    """
    stem, ext = os.path.splitext(dest)
    return f"{stem}.tmp{os.getpid()}{ext}"


def atomic_save_image(img: "Image.Image", dest: str, **save_kwargs) -> None:
    """写入图片并在提交前验证可解码，避免中断/崩溃留下截断文件。

    下游识图提供方（Codex CLI、Google/DashScope 适配器）对损坏/截断图片不报错，
    而是返回“无法识别该图片”的文本，被上层误当成正常识别结果。
    """
    tmp_path = atomic_temp_path(dest)
    try:
        img.save(tmp_path, **save_kwargs)
        with Image.open(tmp_path) as check:
            check.load()
        os.replace(tmp_path, dest)
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def resize_image_if_needed(
    image_path: str, max_side: int = 2048, quality: int = 90,
    output_path: str = None,
) -> str:
    """缩放图片到 max_side 以内。

    Args:
        output_path: 若提供，写入该路径，保留原文件不变；
                     若为 None，覆写原文件（向后兼容）。
    Returns:
        实际写入的路径。
    """
    img = Image.open(image_path)
    w, h = img.size
    dest = output_path or image_path
    if max(w, h) <= max_side:
        if output_path and output_path != image_path:
            shutil.copy2(image_path, output_path)
        return dest
    scale = max_side / max(w, h)
    new_w, new_h = int(w * scale), int(h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    atomic_save_image(img, dest, quality=quality)
    logger.info("[RESIZE] %s: %dx%d -> %dx%d -> %s", image_path, w, h, new_w, new_h, dest)
    return dest


def batch_list(lst: list, batch_size: int) -> list[list]:
    """将列表按指定大小分批。

    Args:
        lst: 原始列表。
        batch_size: 每批大小。

    Returns:
        分批后的嵌套列表。
    """
    return [lst[i:i + batch_size] for i in range(0, len(lst), batch_size)]


def concat_md_files(md_parts: list[str], output_path: str) -> str:
    """合并多段 Markdown 文本并写入文件。

    Args:
        md_parts: Markdown 文本片段列表。
        output_path: 输出文件路径。

    Returns:
        输出文件路径。
    """
    ensure_dir(os.path.dirname(output_path))
    with open(output_path, "w", encoding="utf-8") as f:
        for i, part in enumerate(md_parts):
            f.write(part.strip())
            if i < len(md_parts) - 1:
                f.write("\n\n")
    logger.info("[OUTPUT] 合并 %d 段 Markdown -> %s", len(md_parts), output_path)
    return output_path


def sort_files_by_time(file_paths: list[str]) -> list[str]:
    """按文件修改时间升序排序。

    Args:
        file_paths: 文件路径列表。

    Returns:
        排序后的路径列表。
    """
    return sorted(file_paths, key=lambda p: os.path.getmtime(p))


def strip_md_fence(text: str) -> str:
    """去除 LLM 返回中的 ```markdown ... ``` 包裹。全局唯一实现。"""
    text = text.strip()
    for prefix in ("```markdown", "```md", "```"):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    if text.endswith("```"):
        text = text[:-3].strip()
    return text


def sanitize_llm_markdown(text: str) -> str:
    """清理包裹表格的代码围栏，保留真实代码围栏。"""
    text = text.replace("```markdown", "```").replace("```md", "```")
    lines = text.splitlines()
    sanitized, fence_buf = [], []
    in_fence = False
    fence_open_line = ""

    for line in lines:
        if line.strip().startswith("```"):
            if in_fence:
                if _looks_like_table(fence_buf):
                    sanitized.extend(fence_buf)
                else:
                    sanitized.extend([fence_open_line, *fence_buf, line])
                fence_buf, in_fence, fence_open_line = [], False, ""
            else:
                in_fence = True
                fence_open_line = line
            continue
        (fence_buf if in_fence else sanitized).append(line)

    if in_fence:
        if _looks_like_table(fence_buf):
            sanitized.extend(fence_buf)
        else:
            sanitized.extend([fence_open_line, *fence_buf])
    return "\n".join(sanitized).strip()


def _looks_like_table(lines: list[str]) -> bool:
    non_empty = [l.strip() for l in lines if l.strip()]
    if len(non_empty) < 2:
        return False
    sep_re = re.compile(r"^\|?(?:\s*:?-{3,}:?\s*\|)+(?:\s*:?-{3,}:?\s*)\|?$")
    pipe_lines = [l for l in non_empty if "|" in l]
    if any(sep_re.match(l) for l in non_empty):
        return True
    return len(pipe_lines) >= 2


# ---- 页面元数据: HTML 注释标记 ----
# 新格式: <!-- meta:page number=X -->
# 兼容旧格式: # Page X
_PAGE_META_RE = re.compile(
    r"^<!--\s*meta:page\s+number=(\d+)\s*-->$", flags=re.IGNORECASE
)
_PAGE_HEADER_LEGACY_RE = re.compile(
    r"^#\s+Page\s+(\d+)", flags=re.IGNORECASE
)


def _is_page_marker(line: str) -> bool:
    """检查是否为页面标记（新 HTML 注释格式或旧 # Page X 格式）。"""
    stripped = line.strip()
    if _PAGE_META_RE.match(stripped):
        return True
    return bool(re.match(r"^#\s+Page\s+.+$", stripped, flags=re.IGNORECASE))


def _extract_page_number(line: str) -> int | None:
    """从页面标记中提取页码，支持新旧格式。"""
    stripped = line.strip()
    m = _PAGE_META_RE.match(stripped)
    if m:
        return int(m.group(1))
    m = _PAGE_HEADER_LEGACY_RE.match(stripped)
    if m:
        return int(m.group(1))
    return None


def _is_top_level_header(line: str) -> bool:
    return bool(re.match(r"^#(?!#)\s+", line.strip()))


def demote_non_page_headers(text: str) -> str:
    """将所有一级标题降级为二级标题（页标记已改为 HTML 注释，不再有 # Page X）。

    Args:
        text: Markdown 文本。

    Returns:
        处理后的文本。
    """
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if _is_top_level_header(stripped):
            lines[idx] = f"## {stripped[2:].lstrip()}"
    return "\n".join(lines).strip()


def normalize_single_page_markdown(text: str, page_num: int) -> str:
    """标准化单页 Markdown：移除多余页标记，确保仅一个页标记。

    Args:
        text: 单页 Markdown。
        page_num: 页码。

    Returns:
        标准化后的 Markdown。
    """
    body_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if _is_page_marker(stripped):
            continue
        if _is_top_level_header(stripped):
            body_lines.append(f"## {stripped[2:].lstrip()}")
            continue
        body_lines.append(line)

    body = "\n".join(body_lines).strip()
    if not body:
        return f"<!-- meta:page number={page_num} -->"
    return f"<!-- meta:page number={page_num} -->\n\n{body}"


def normalize_page_headers(text: str, start_page: int, expected_pages: int) -> str:
    """标准化多页 Markdown 中的页标记序号（支持新旧格式输入，统一输出新格式）。

    Args:
        text: 多页 Markdown 文本。
        start_page: 起始页码。
        expected_pages: 预期页数。

    Returns:
        标准化后的文本。
    """
    lines = text.splitlines()
    next_page, replaced = start_page, 0
    for idx, line in enumerate(lines):
        if _is_page_marker(line):
            if replaced < expected_pages:
                lines[idx] = f"<!-- meta:page number={next_page} -->"
                next_page += 1
                replaced += 1
            else:
                # 多余的页标记移除
                lines[idx] = ""
    return demote_non_page_headers("\n".join(lines).strip())


def count_page_headers(text: str) -> int:
    """统计文本中页标记的数量（支持新旧格式）。

    Args:
        text: Markdown 文本。

    Returns:
        页标记数量。
    """
    new_count = len(re.findall(
        r"^<!--\s*meta:page\s+number=\d+\s*-->$", text, flags=re.MULTILINE | re.IGNORECASE,
    ))
    old_count = len(re.findall(r"^#\s+Page\s+.+$", text, flags=re.MULTILINE | re.IGNORECASE))
    return new_count + old_count


def _iter_ffmpeg_tool_dirs() -> list[Path]:
    """返回 ffmpeg/ffprobe 可能所在的目录列表。"""
    candidates: list[Path] = []
    seen: set[Path] = set()

    def _add(path_like: str | Path | None):
        if not path_like:
            return
        path = Path(path_like).expanduser()
        if path.is_file():
            path = path.parent
        if path in seen or not path.exists():
            return
        seen.add(path)
        candidates.append(path)

    _add(os.getenv("OCRLLM_FFMPEG_DIR"))
    _add(os.getenv("FFMPEG_DIR"))
    _add(os.getenv("FFMPEG_ROOT"))
    _add(os.getenv("IMAGEIO_FFMPEG_EXE"))

    conda_prefix = os.getenv("CONDA_PREFIX")
    if conda_prefix:
        _add(conda_prefix)
        _add(Path(conda_prefix) / "Library" / "bin")
        _add(Path(conda_prefix) / "Scripts")

    python_dir = Path(sys.executable).resolve().parent
    _add(python_dir)
    _add(python_dir.parent / "Library" / "bin")
    _add(python_dir.parent / "Scripts")

    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        _add(Path(local_app_data) / "Microsoft" / "WinGet" / "Links")
        _add(Path(local_app_data) / "Programs" / "ffmpeg" / "bin")
        winget_packages = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_packages.exists():
            for match in winget_packages.glob("*/ffmpeg*/bin"):
                _add(match)

    _add(Path(r"C:\ffmpeg\bin"))
    _add(Path(r"C:\Program Files\ffmpeg\bin"))
    _add(Path(r"C:\Program Files (x86)\ffmpeg\bin"))

    return candidates


def _find_av_tool(binary_name: str) -> str | None:
    """在 PATH 和常见安装目录中查找音视频工具。"""
    resolved = shutil.which(binary_name)
    if resolved:
        return resolved

    suffix = ".exe" if os.name == "nt" else ""
    file_name = binary_name if binary_name.endswith(suffix) else f"{binary_name}{suffix}"
    for directory in _iter_ffmpeg_tool_dirs():
        candidate = directory / file_name
        if candidate.is_file():
            return str(candidate)
    return None


def get_ffmpeg() -> str:
    """查找 ffmpeg 可执行文件。全局唯一实现。"""
    ffmpeg = _find_av_tool("ffmpeg")
    if ffmpeg:
        return ffmpeg
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        if ffmpeg and os.path.isfile(ffmpeg):
            return ffmpeg
    except ImportError:
        pass
    raise RuntimeError("ffmpeg 未找到！pip install imageio-ffmpeg 或安装 ffmpeg 到 PATH")


def get_ffprobe() -> str:
    """查找 ffprobe 可执行文件。"""
    ffprobe = _find_av_tool("ffprobe")
    if ffprobe:
        return ffprobe

    ffmpeg_path = Path(get_ffmpeg())
    candidate = ffmpeg_path.with_name(f"ffprobe{ffmpeg_path.suffix}")
    if candidate.is_file():
        return str(candidate)

    raise RuntimeError(
        "ffprobe 未找到；当前将回退到 ffmpeg 探测时长。"
        "如需启用 ffprobe，可安装 ffmpeg/ffprobe，或设置 OCRLLM_FFMPEG_DIR / FFMPEG_DIR。"
    )


def _default_log_file() -> Path:
    override = os.environ.get("OCRLLM_LOG_FILE", "").strip()
    if override:
        return Path(override)
    return Path.cwd() / "logs" / "ocrllm.log"


def setup_logging(level=logging.INFO, log_file: str | os.PathLike | None = None):
    """配置全局日志格式，并降低 httpx/openai 等第三方库的日志级别。

    Args:
        level: 日志级别，默认 INFO。
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    root = logging.getLogger()
    root.setLevel(level)

    log_path = Path(log_file) if log_file is not None else _default_log_file()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_log_path = log_path.resolve()

    for handler in list(root.handlers):
        if getattr(handler, _PERSISTENT_LOG_MARKER, False):
            current = Path(getattr(handler, "baseFilename", "")).resolve()
            if current == resolved_log_path:
                handler.setLevel(level)
                break
            root.removeHandler(handler)
            handler.close()
    else:
        handler = RotatingFileHandler(
            resolved_log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        setattr(handler, _PERSISTENT_LOG_MARKER, True)
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "%Y-%m-%d %H:%M:%S",
        ))
        root.addHandler(handler)
        logger.info("[LOG] persistent log file: %s", resolved_log_path)
    # 抑制第三方网络库的 DEBUG 日志，避免 GUI 轮询时刷屏。
    for noisy in ("httpx", "openai", "httpcore", "urllib3", "requests", "charset_normalizer"):
        logging.getLogger(noisy).setLevel(max(level, logging.WARNING))


def windows_no_window_kwargs() -> dict:
    """Windows 上构造避免新建黑色 cmd 窗口的 Popen 参数。其他平台返回空字典。

    GUI 进程从 PyQt5 启动 ffmpeg/ffprobe/yt-dlp 时若不指定 CREATE_NO_WINDOW，
    Windows 会为子进程附加一个一闪而过的控制台窗口。
    """
    if sys.platform != "win32":
        return {}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0  # SW_HIDE
    return {"creationflags": flags, "startupinfo": startupinfo}


def run_subprocess_cancellable(
    cmd: list[str],
    cancel_event: threading.Event | None = None,
    timeout: float = 600,
    poll_interval: float = 0.5,
    check: bool = False,
    text: bool = False,
    **popen_kwargs,
) -> subprocess.CompletedProcess:
    """类似 subprocess.run，但支持通过 cancel_event 协作式取消。

    用线程异步读取 stdout/stderr 防止管道缓冲区满导致死锁，
    主线程轮询 cancel_event 和超时。
    """
    from OCRLLM.core.task_runner import CancelledError

    popen_kwargs.setdefault("stdout", subprocess.PIPE)
    popen_kwargs.setdefault("stderr", subprocess.PIPE)
    for key, value in windows_no_window_kwargs().items():
        popen_kwargs.setdefault(key, value)
    proc = subprocess.Popen(cmd, **popen_kwargs)
    deadline = time.monotonic() + timeout if timeout else None

    # 后台线程读取管道，避免缓冲区满阻塞子进程
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []

    def _drain(pipe, chunks):
        while True:
            data = pipe.read(8192)
            if not data:
                break
            chunks.append(data)

    readers = []
    if proc.stdout:
        t = threading.Thread(target=_drain, args=(proc.stdout, stdout_chunks), daemon=True)
        t.start()
        readers.append(t)
    if proc.stderr:
        t = threading.Thread(target=_drain, args=(proc.stderr, stderr_chunks), daemon=True)
        t.start()
        readers.append(t)

    try:
        while proc.poll() is None:
            if cancel_event and cancel_event.is_set():
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                raise CancelledError("任务已取消")
            if deadline and time.monotonic() > deadline:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                raise subprocess.TimeoutExpired(cmd, timeout)
            time.sleep(poll_interval)
    except (CancelledError, subprocess.TimeoutExpired):
        raise
    except BaseException:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        raise
    finally:
        for t in readers:
            t.join(timeout=5)

    stdout_data = b"".join(stdout_chunks) if stdout_chunks else b""
    stderr_data = b"".join(stderr_chunks) if stderr_chunks else b""
    if text:
        stdout_data = stdout_data.decode("utf-8", errors="replace")
        stderr_data = stderr_data.decode("utf-8", errors="replace")

    result = subprocess.CompletedProcess(cmd, proc.returncode, stdout_data, stderr_data)
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, stdout_data, stderr_data)
    return result
