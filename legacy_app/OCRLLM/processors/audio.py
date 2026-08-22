"""
语音识别处理器 — 支持短音频（qwen3-asr-flash）和长音频（filetrans 异步）。
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import ssl
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib.parse import urlsplit, urlunsplit
from urllib3.util.ssl_ import create_urllib3_context

from OCRLLM.core.task_runner import CancelledError
from OCRLLM.core.checkpoint import Checkpoint
from OCRLLM.core.provider_selection import uses_google_for_audio
from OCRLLM.core.utils import ensure_dir, get_ffmpeg, get_ffprobe, resolve_workers, run_subprocess_cancellable, strip_md_fence
from OCRLLM.processors.base import BaseProcessor
from OCRLLM.processors.audio_filetrans_task_state import (
    clear_filetrans_task_state,
    load_filetrans_task_id,
    save_filetrans_task_state,
)
from OCRLLM.core.document_model import SourceType
from OCRLLM import prompts

logger = logging.getLogger(__name__)


class ASRNoValidFragmentError(RuntimeError):
    """DashScope filetrans accepted the task but found no valid speech fragment."""


_DASHSCOPE_NATIVE_FORMATS = {".wav", ".mp3", ".m4a", ".flac", ".opus", ".aac", ".amr"}

_DASHSCOPE_RESULT_HOSTS = {
    "dashscope-result-bj.oss-cn-beijing.aliyuncs.com",
    "dashscope-file-mgr.oss-cn-beijing.aliyuncs.com",
}


@dataclass(frozen=True)
class AudioChunk:
    path: str
    actual_start: float
    actual_end: float
    logical_start: float
    logical_end: float


@dataclass(frozen=True)
class AudioWindow:
    actual_start: float
    actual_end: float
    logical_start: float
    logical_end: float


@dataclass(frozen=True)
class AudioSignalStats:
    mean_volume_db: float | None = None
    max_volume_db: float | None = None


_GOOGLE_WEAK_AUDIO_MIN_DURATION = 30 * 60
_GOOGLE_WEAK_AUDIO_MEAN_DB = -55.0
_GOOGLE_WEAK_AUDIO_MAX_DB = -35.0
_GOOGLE_TOPIC_MIN_TERMS = 5
_GOOGLE_TOPIC_MIN_TEXT_CHARS = 4000

_TOPIC_TERM_STOPWORDS = {
    "about",
    "above",
    "after",
    "before",
    "course",
    "example",
    "lecture",
    "method",
    "problem",
    "question",
    "section",
    "teacher",
    "today",
}

_TRANSCRIPT_TIMESTAMP_RE = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")
_HOTWORD_MARKER_RE = re.compile(r"(?:热词|术语|关键词|专业词)(?:表|列表)?")
_SENTENCE_PUNCT_RE = re.compile(r"[。！？!?]")
_MODEL_SEGMENT_RE = re.compile(
    r"^<!--\s*meta:segment\s+(?P<attrs>.*?)\s*-->\s*$",
    flags=re.IGNORECASE,
)
_MODEL_SEGMENT_TIME_RE = re.compile(r"\btime=(?P<time>\S+)")


def build_fallback_audio_windows(
    duration: float,
    chunk_seconds: int = 360,
    context_seconds: int = 30,
) -> list[AudioWindow]:
    """Build long-audio fallback windows with clamped head/tail context."""
    if duration <= 0:
        return []
    chunk = max(1, int(chunk_seconds))
    context = max(0, int(context_seconds))
    windows: list[AudioWindow] = []
    logical_start = 0.0
    while logical_start < duration:
        logical_end = min(duration, logical_start + chunk)
        actual_start = max(0.0, logical_start - context)
        actual_end = min(duration, logical_end + context)
        if actual_end > actual_start:
            windows.append(AudioWindow(actual_start, actual_end, logical_start, logical_end))
        logical_start = logical_end
    return windows


def build_google_audio_windows(
    duration: float,
    chunk_seconds: int = 30 * 60,
    overlap_seconds: int = 30,
) -> list[AudioWindow]:
    """Build Google audio windows: 30-minute logical chunks with overlap context."""
    return build_fallback_audio_windows(
        duration=duration,
        chunk_seconds=chunk_seconds,
        context_seconds=overlap_seconds,
    )


def _derive_asr_api_root(base_url: str) -> str:
    """从主 API Base URL 派生出 DashScope 原生 API 根路径。

    base_url 可能是 https://dashscope.aliyuncs.com/compatible-mode/v1
    → 提取 scheme + host，去掉 /compatible-mode 部分，得到
    https://dashscope.aliyuncs.com
    """
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(base_url)
    path = parsed.path.rstrip("/")
    # 去掉 /compatible-mode/v1 （或 /compatible-mode）后缀
    if "/compatible-mode" in path:
        path = path.split("/compatible-mode")[0]
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def _get_trusted_hosts(base_url: str) -> set[str]:
    """返回可信的主机名集合（包含配置的 API 主机 + OSS 结果存储主机）。"""
    from urllib.parse import urlparse
    host = urlparse(base_url).hostname
    hosts = set(_DASHSCOPE_RESULT_HOSTS)
    if host:
        hosts.add(host)
    return hosts


def _is_trusted_url(url: str, trusted_hosts: set[str]) -> bool:
    """仅允许白名单 host，下载链接可由 HTTP 自动升级为 HTTPS。"""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.hostname in trusted_hosts and parsed.scheme in {"https", "http"}


def _normalize_trusted_url(url: str, trusted_hosts: set[str]) -> str | None:
    """校验并标准化可访问 URL。结果下载 URL 允许 HTTP，统一升级为 HTTPS。"""
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(url)
    if parsed.hostname not in trusted_hosts:
        return None
    if parsed.scheme not in {"https", "http"}:
        return None
    if parsed.scheme == "http":
        parsed = parsed._replace(scheme="https")
    return urlunparse(parsed)


def audio_markdown_body(md: str) -> str:
    """Return transcript body without OCRLLM metadata blockquotes/comments."""
    body_lines: list[str] = []
    for line in md.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("<!--") and stripped.endswith("-->"):
            continue
        if stripped.startswith(">"):
            continue
        body_lines.append(line)
    return "\n".join(body_lines).strip()


def _clean_topic_term(value: str) -> str:
    term = re.sub(r"\s+", " ", str(value or "")).strip()
    return term.strip(" \t\r\n-_*#`~:：,，.。;；|/\\()[]{}<>")


def _dedupe_topic_terms(expected_terms: list[str] | tuple[str, ...] | None) -> list[str]:
    if not expected_terms:
        return []
    terms: list[str] = []
    seen: set[str] = set()
    for raw in expected_terms:
        term = _clean_topic_term(str(raw))
        if len(term) < 2 or len(term) > 60:
            continue
        key = term.casefold()
        if key in _TOPIC_TERM_STOPWORDS or key.isdigit() or key in seen:
            continue
        seen.add(key)
        terms.append(term)
    return terms


def _count_topic_hits(text: str, expected_terms: list[str]) -> int:
    lower_text = text.casefold()
    compact_text = re.sub(r"\s+", "", lower_text)
    hits = 0
    for term in expected_terms:
        needle = term.casefold()
        compact_needle = re.sub(r"\s+", "", needle)
        if needle in lower_text or (compact_needle and compact_needle in compact_text):
            hits += 1
    return hits


def _google_topic_mismatch_reason(text: str, expected_terms: list[str] | tuple[str, ...] | None) -> str | None:
    terms = _dedupe_topic_terms(expected_terms)
    if len(terms) < _GOOGLE_TOPIC_MIN_TERMS or len(text) < _GOOGLE_TOPIC_MIN_TEXT_CHARS:
        return None
    hits = _count_topic_hits(text, terms)
    required_hits = min(6, max(2, len(terms) // 8))
    hit_ratio = hits / max(1, len(terms))
    if hits < required_hits and hit_ratio < 0.08:
        return f"topic mismatch: matched {hits}/{len(terms)} expected terms, need at least {required_hits}"
    return None


def _timestamp_only_reason(text: str) -> str | None:
    sample = text[:10000]
    timestamps = _TRANSCRIPT_TIMESTAMP_RE.findall(sample)
    if len(timestamps) < 60:
        return None
    residue = _TRANSCRIPT_TIMESTAMP_RE.sub(" ", sample)
    residue = re.sub(r"[\s,，.。;；:：/\\|()[\]{}<>_\-+=*#`~]+", "", residue)
    nonspace_chars = len(re.sub(r"\s+", "", sample))
    if len(residue) < max(80, int(nonspace_chars * 0.05)):
        return f"timestamp-only output: {len(timestamps)} timestamps with almost no speech text"
    return None


def _repeated_filler_reason(text: str) -> str | None:
    sample = text[:10000]
    filler_tokens = re.findall(r"[嗯啊呃额哎哦诶唔]{1,3}", sample)
    if len(filler_tokens) < 80:
        return None
    residue = re.sub(r"[嗯啊呃额哎哦诶唔\s,，.。;；:：!！?？~～-]+", "", sample)
    nonspace_chars = len(re.sub(r"\s+", "", sample))
    if len(residue) < max(80, int(nonspace_chars * 0.10)):
        return f"repeated filler output: {len(filler_tokens)} filler tokens with almost no speech text"
    return None


def _repeated_hotword_echo_reason(
    text: str,
    expected_terms: list[str] | tuple[str, ...] | None = None,
) -> str | None:
    sample = text[:20000]
    marker_count = len(_HOTWORD_MARKER_RE.findall(sample))
    raw_lines = [line.strip() for line in sample.splitlines() if line.strip()]
    short_lines = []
    for line in raw_lines:
        if line.startswith("<!--"):
            continue
        cleaned = _clean_topic_term(line)
        if 2 <= len(cleaned) <= 80 and not _SENTENCE_PUNCT_RE.search(line):
            short_lines.append(cleaned)

    if short_lines:
        repeated_short_lines = sum(
            count for count in Counter(line.casefold() for line in short_lines).values()
            if count >= 3
        )
        if marker_count >= 2 and len(short_lines) >= 12 and len(short_lines) >= int(len(raw_lines) * 0.6):
            return f"正文夹杂重复热词列表: {marker_count} 个热词标记，{len(short_lines)} 行短术语"
        if repeated_short_lines >= 20 and (marker_count >= 1 or repeated_short_lines >= int(len(short_lines) * 0.5)):
            return f"正文夹杂重复热词短行: {repeated_short_lines} 行重复术语"

    terms = _dedupe_topic_terms(expected_terms)
    if len(terms) < 3:
        return None
    lower_text = sample.casefold()
    compact_text = re.sub(r"\s+", "", lower_text)
    compact_len = len(compact_text)
    if compact_len <= 0:
        return None

    distinct_hits = 0
    occurrence_count = 0
    matched_chars = 0
    for term in terms:
        needle = term.casefold()
        compact_needle = re.sub(r"\s+", "", needle)
        count = lower_text.count(needle)
        if count == 0 and compact_needle and compact_needle != needle:
            count = compact_text.count(compact_needle)
        if count <= 0:
            continue
        distinct_hits += 1
        occurrence_count += count
        matched_chars += len(compact_needle or needle) * count

    density = matched_chars / compact_len
    if (
        distinct_hits >= min(4, len(terms))
        and occurrence_count >= max(20, len(terms) * 3)
        and density >= 0.35
    ):
        return (
            f"正文被重复热词占据: 命中 {distinct_hits}/{len(terms)} 个热词，"
            f"出现 {occurrence_count} 次，热词密度 {density:.0%}"
        )
    return None


def google_audio_transcript_invalid_reason(
    text: str,
    duration: float | None = None,
    expected_terms: list[str] | tuple[str, ...] | None = None,
) -> str | None:
    """Detect Google long-audio false successes before they are written as transcripts."""
    stripped = text.strip()
    if not stripped:
        return "返回空内容"

    head = stripped[:240]
    if "请把这段课程录音尽量逐字转写成中文文本" in head or "只输出转写内容本身" in head:
        return "正文包含提示词回显，不是纯课堂语音转写"
    if (
        ("根据您提供" in head or "基于你刚才识别" in head or "板书" in head)
        and ("热词" in head or "术语" in head or "专业词" in head)
    ):
        return "正文像热词表/术语表，不是课堂语音转写"

    if re.search(r"(你[，。,.、\s]*){30,}", stripped[:5000]):
        return "正文包含大段重复噪声"

    hotword_reason = _repeated_hotword_echo_reason(stripped, expected_terms)
    if hotword_reason:
        return hotword_reason

    timestamp_reason = _timestamp_only_reason(stripped)
    if timestamp_reason:
        return timestamp_reason

    filler_reason = _repeated_filler_reason(stripped)
    if filler_reason:
        return filler_reason

    if duration and duration >= 30 * 60:
        duration_minutes = duration / 60.0
        min_chars = max(4000, int(duration_minutes * 80))
        if len(stripped) < min_chars:
            return f"转写正文过短: {len(stripped)} 字，音频约 {duration_minutes:.1f} 分钟，最低期望 {min_chars} 字"

    topic_reason = _google_topic_mismatch_reason(stripped, expected_terms)
    if topic_reason:
        return topic_reason

    return None


def _parse_db_value(value: str) -> float | None:
    normalized = value.strip().lower()
    if normalized == "-inf":
        return float("-inf")
    try:
        return float(normalized)
    except ValueError:
        return None


def parse_ffmpeg_volumedetect(output: str) -> AudioSignalStats:
    mean_volume_db = None
    max_volume_db = None
    mean_match = re.search(r"mean_volume:\s*([-+]?(?:\d+(?:\.\d+)?|inf|-inf))\s*dB", output, flags=re.IGNORECASE)
    max_match = re.search(r"max_volume:\s*([-+]?(?:\d+(?:\.\d+)?|inf|-inf))\s*dB", output, flags=re.IGNORECASE)
    if mean_match:
        mean_volume_db = _parse_db_value(mean_match.group(1))
    if max_match:
        max_volume_db = _parse_db_value(max_match.group(1))
    return AudioSignalStats(mean_volume_db=mean_volume_db, max_volume_db=max_volume_db)


def measure_audio_signal(audio_path: str, cancel_event=None) -> AudioSignalStats:
    ffmpeg = get_ffmpeg()
    result = run_subprocess_cancellable(
        [
            ffmpeg,
            "-hide_banner",
            "-i",
            audio_path,
            "-vn",
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ],
        cancel_event=cancel_event,
        timeout=1800,
        text=True,
        check=False,
    )
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    stats = parse_ffmpeg_volumedetect(output)
    if stats.mean_volume_db is None and stats.max_volume_db is None:
        raise RuntimeError(f"无法解析音频响度: {audio_path}")
    return stats


def google_audio_signal_invalid_reason(stats: AudioSignalStats, duration: float | None = None) -> str | None:
    if not duration or duration < _GOOGLE_WEAK_AUDIO_MIN_DURATION:
        return None
    if stats.mean_volume_db is None:
        return None
    if (
        stats.mean_volume_db <= _GOOGLE_WEAK_AUDIO_MEAN_DB
        and (stats.max_volume_db is None or stats.max_volume_db <= _GOOGLE_WEAK_AUDIO_MAX_DB)
    ):
        max_part = ""
        if stats.max_volume_db is not None:
            max_part = f"，峰值 {stats.max_volume_db:.1f} dB"
        return (
            f"音轨整体响度过低: 均值 {stats.mean_volume_db:.1f} dB{max_part}，"
            f"音频约 {duration / 60.0:.1f} 分钟，疑似没有可识别课堂语音"
        )
    return None


def validate_google_audio_transcript(
    text: str,
    duration: float | None = None,
    expected_terms: list[str] | tuple[str, ...] | None = None,
):
    reason = google_audio_transcript_invalid_reason(text, duration=duration, expected_terms=expected_terms)
    if reason:
        raise RuntimeError(f"Google 长音频识别疑似假成功: {reason}")


def google_audio_transcript_md_valid(
    md_path: str,
    duration: float | None = None,
    expected_terms: list[str] | tuple[str, ...] | None = None,
) -> bool:
    try:
        with open(md_path, encoding="utf-8") as f:
            body = audio_markdown_body(f.read())
    except OSError:
        return False
    return google_audio_transcript_invalid_reason(body, duration=duration, expected_terms=expected_terms) is None


def _retry_on_ssl(fn, max_retries=3, base_delay=5, sleep_fn=None):
    for attempt in range(max_retries):
        try:
            return fn()
        except (
            requests.exceptions.SSLError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            ConnectionResetError,
            TimeoutError,
            OSError,
        ) as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning(
                "[ASR] 网络错误 (重试 %d/%d, %ds后重试): %s",
                attempt + 1,
                max_retries,
                delay,
                type(e).__name__,
            )
            if sleep_fn:
                sleep_fn(delay)
            else:
                time.sleep(delay)


class _TLS12HttpAdapter(HTTPAdapter):
    """为 requests 强制注入 TLS 1.2+ 上下文。"""

    @staticmethod
    def _build_context():
        context = create_urllib3_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        return context

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self._build_context()
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs["ssl_context"] = self._build_context()
        return super().proxy_manager_for(*args, **kwargs)


class AudioProcessor(BaseProcessor):
    """语音识别处理器。"""

    processor_key = "audio"
    display_name = "语音识别"

    # ---- URL 构建（从主 API base_url 派生） ----

    @property
    def _asr_api_root(self) -> str:
        """DashScope 原生 API 根路径（从主 API base_url 派生）。"""
        return _derive_asr_api_root(self.cfg.api.base_url)

    @property
    def _submit_url(self) -> str:
        return f"{self._asr_api_root}/api/v1/services/audio/asr/transcription"

    @property
    def _task_url_template(self) -> str:
        return f"{self._asr_api_root}/api/v1/tasks/{{task_id}}"

    @property
    def _files_url(self) -> str:
        return f"{self._asr_api_root}/api/v1/files"

    @property
    def _trusted_hosts(self) -> set[str]:
        return _get_trusted_hosts(self._asr_api_root)
    supported_extensions = (".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma")
    source_type = SourceType.AUDIO

    def _get_ffprobe_path(self) -> str:
        """懒加载 ffprobe 路径，避免同一处理器实例内重复查找。"""
        ffprobe_path = getattr(self, "_ffprobe_path", None)
        if ffprobe_path is None:
            try:
                ffprobe_path = get_ffprobe()
            except RuntimeError as e:
                logger.info("[ASR] 未找到 ffprobe，使用 ffmpeg 兼容探测时长: %s", e)
                ffprobe_path = ""
            self._ffprobe_path = ffprobe_path
        return ffprobe_path

    def _get_http_session(self) -> requests.Session:
        session = getattr(self, "_http_session", None)
        if session is None:
            session = requests.Session()
            adapter = _TLS12HttpAdapter(max_retries=0)
            session.mount("https://", adapter)
            self._http_session = session
        return session

    def _close_http_session(self):
        """显式关闭 HTTP session，释放连接池资源。"""
        session = getattr(self, "_http_session", None)
        if session is not None:
            try:
                session.close()
            except Exception:
                pass
            self._http_session = None

    def _get_cached_duration(self, audio_path: str) -> float:
        """按文件路径和文件状态缓存时长探测结果。"""
        cache = getattr(self, "_duration_cache", None)
        if cache is None:
            cache = {}
            self._duration_cache = cache

        abs_path = os.path.abspath(audio_path)
        try:
            stat = os.stat(abs_path)
            cache_key = (abs_path, stat.st_size, stat.st_mtime_ns)
        except OSError:
            cache_key = (abs_path, -1, -1)

        duration = cache.get(cache_key)
        if duration is None:
            duration = _probe_duration(
                abs_path,
                ffprobe_path=self._get_ffprobe_path(),
                cancel_event=self.reporter.cancel_event,
            )
            cache[cache_key] = duration
            # M10: 限制缓存大小，防止长时间运行时无限增长
            if len(cache) > 256:
                oldest_key = next(iter(cache))
                cache.pop(oldest_key, None)
        return duration

    @staticmethod
    def _filetrans_input_summary(audio_path: str, duration: float | None) -> str:
        if _is_remote(audio_path):
            parsed = urlsplit(audio_path)
            safe_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
            return f"url={safe_url}, duration=unknown"

        path = Path(audio_path)
        parts = [
            f"path={path}",
            f"ext={path.suffix.lower() or '<none>'}",
        ]
        try:
            parts.append(f"size={path.stat().st_size / (1024 * 1024):.2f}MB")
        except OSError as exc:
            parts.append(f"size=unavailable({exc})")

        if duration is None:
            parts.append("duration=unknown")
        else:
            parts.append(f"duration={duration:.1f}s")
        return ", ".join(parts)

    @staticmethod
    def _filetrans_visible_text_chars(markdown: str) -> int:
        without_meta = re.sub(r"<!--.*?-->", "", markdown, flags=re.DOTALL)
        return len(re.findall(r"[\w\u4e00-\u9fff]", without_meta, flags=re.UNICODE))

    @classmethod
    def _filetrans_text_quality_warning(cls, markdown: str, duration: float | None) -> str | None:
        if duration is None or duration < 10 * 60:
            return None
        visible_chars = cls._filetrans_visible_text_chars(markdown)
        threshold = max(80, min(500, int((duration / 60.0) * 5)))
        if visible_chars < threshold:
            return f"识别文本过短: {visible_chars} 字符，音频 {duration:.1f}s，最低期望 {threshold} 字符"
        return None

    @staticmethod
    def _append_filetrans_warning(markdown: str, warning: str, input_summary: str) -> str:
        return (
            markdown.rstrip()
            + "\n\n"
            + "> [!WARNING]\n"
            + f"> 音频识别质量警告: {warning}\n"
            + f"> 输入: {input_summary}\n"
        )

    @staticmethod
    def _filetrans_warning_markdown(title: str, warning: str, input_summary: str) -> str:
        return (
            f"<!-- meta:audio title={title} -->\n\n"
            + "> [!WARNING]\n"
            + f"> 音频识别质量警告: {warning}\n"
            + f"> 输入: {input_summary}\n"
        )

    def process(
        self,
        audio_path: str,
        hotwords: Optional[list[str]] = None,
        output_path: str = None,
        poll_interval: float = 5.0,
        max_wait: float = 3600,
        prompt_template: str = None,
        resume: bool = False,
    ) -> str:
        """执行语音识别：自动选择短音频或长音频异步模式。

        Args:
            audio_path: 音频文件路径或远程 URL。
            hotwords: 热词列表，提高识别准确率。
            output_path: 输出 Markdown 路径，None 则自动生成。
            poll_interval: 异步任务轮询间隔（秒）。
            max_wait: 异步任务最大等待时间（秒）。
            prompt_template: 自定义提示词模板。

        Returns:
            输出文件路径。
        """
        use_google_audio = uses_google_for_audio(self.cfg)
        logger.info(
            "[ASR] route=%s google_enabled=%s audio_model=%s google_audio_model=%s",
            "google" if use_google_audio else "filetrans",
            self.cfg.google_api.enabled,
            self.cfg.models.asr_model,
            self.cfg.google_api.audio_model,
        )
        if use_google_audio:
            return self._process_google_long_audio(
                audio_path,
                hotwords=hotwords,
                output_path=output_path,
                prompt_template=prompt_template,
                resume=resume,
            )

        if not self.cfg.api.api_key:
            raise ValueError(
                "未配置 API Key。请设置环境变量 DASHSCOPE_API_KEY 或在配置中提供 api_key"
            )
        stem = Path(audio_path).stem if not audio_path.startswith("http") else "audio"
        if output_path is None:
            output_path = os.path.join(ensure_dir(self.cfg.paths.output_dir), f"{stem}_录音识别.md")

        actual_path = audio_path
        if not _is_remote(audio_path):
            actual_path = self._ensure_upload_format(audio_path)

        if not _is_remote(actual_path):
            use_short, duration = self._should_use_short_asr(actual_path)
            if use_short:
                self._report(1, 5, f"使用短音频模型: {self.cfg.models.asr_short_model}")
                return self._short_asr(actual_path, hotwords, output_path, prompt_template, duration=duration)
        else:
            duration = None

        filetrans_input_summary = self._filetrans_input_summary(actual_path, duration)

        try:
            self._report(1, 5, f"使用长音频异步模型: {self.cfg.models.asr_model}")
            logger.info(
                "[ASR] filetrans input: model=%s, %s",
                self.cfg.models.asr_model,
                filetrans_input_summary,
            )
            task_id = None
            if resume:
                task_id = load_filetrans_task_id(
                    output_path,
                    model=self.cfg.models.asr_model,
                    audio_path=actual_path,
                )
                if task_id:
                    logger.info("[ASR] 继续等待已有 filetrans 任务: task_id=%s", task_id)
                    self._report(3, 5, f"继续等待语音识别任务: {task_id}")

            if not task_id:
                if _is_remote(actual_path):
                    file_url = actual_path
                else:
                    self._report(2, 5, "上传音频文件...")
                    file_url = self._upload_file(actual_path)

                self._report(3, 5, "提交语音识别任务...")
                task_id = self._submit_task(file_url, hotwords)
                save_filetrans_task_state(
                    output_path,
                    task_id=task_id,
                    model=self.cfg.models.asr_model,
                    audio_path=actual_path,
                    file_url=file_url,
                )

            self._report(4, 5, "等待识别完成...")
            result = self._wait_result(task_id, poll_interval, max_wait)

            self._report(5, 5, "生成 Markdown...")
            try:
                md = self._result_to_md(result, stem)
            except RuntimeError as e:
                warning = f"filetrans 任务完成，但未返回转写正文: {e}"
                logger.warning("[ASR] %s; input=%s", warning, filetrans_input_summary)
                md = self._filetrans_warning_markdown(stem, warning, filetrans_input_summary)

            quality_warning = self._filetrans_text_quality_warning(md, duration)
            if quality_warning:
                logger.warning("[ASR] filetrans 返回内容过少，继续输出警告: %s; input=%s", quality_warning, filetrans_input_summary)
                md = self._append_filetrans_warning(md, quality_warning, filetrans_input_summary)
            self._report_content(md, "语音识别完成")

            ensure_dir(os.path.dirname(output_path))
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(md)
            clear_filetrans_task_state(output_path)

            try:
                audio_duration = self._get_cached_duration(actual_path)
                est_cost = audio_duration * 0.22 / 1000
                logger.info(
                    f"[ASR] 长音频识别完成: {stem}, 时长 {audio_duration:.1f}s, "
                    f"按官网价格 (0.22 元/千秒) 预计费用约 {est_cost:.3f} 元")
            except Exception as e:
                logger.warning(f"[ASR] 无法计算音频时长用于成本预估: {e}")
            self._report(5, 5, f"完成: {output_path}")
            return output_path
        except ASRNoValidFragmentError as e:
            warning = f"filetrans 未检测到有效语音片段: {e}"
            logger.warning("[ASR] %s; input=%s", warning, filetrans_input_summary)
            md = self._filetrans_warning_markdown(stem, warning, filetrans_input_summary)
            self._report_content(md, "语音识别完成（有警告）")

            ensure_dir(os.path.dirname(output_path))
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(md)
            clear_filetrans_task_state(output_path)

            self._report(5, 5, f"完成（音频识别有警告）: {output_path}")
            return output_path
        except Exception as e:
            logger.error("[ASR] 长音频异步处理失败: %s; input=%s", e, filetrans_input_summary)
            raise RuntimeError(
                f"长音频异步识别失败。输入: {filetrans_input_summary}。原始错误: {e}"
            ) from e
        finally:
            self._close_http_session()

    # ---- Repair: re-transcribe failed segments in an existing short-ASR output ----

    _FAILED_SEGMENT_RE = re.compile(
        r"（分段\s+(\d+)\s+(?:识别失败|未完成)(?::.*?)?）",
    )

    @staticmethod
    def find_failed_segments(md_path: str) -> list[int]:
        """Return 1-based segment indices that have failure markers."""
        try:
            text = Path(md_path).read_text(encoding="utf-8")
        except OSError:
            return []
        indices: list[int] = []
        for m in AudioProcessor._FAILED_SEGMENT_RE.finditer(text):
            idx = int(m.group(1))
            if idx not in indices:
                indices.append(idx)
        return sorted(indices)

    def repair(
        self,
        audio_path: str,
        md_path: str,
        hotwords: Optional[list[str]] = None,
        prompt_template: str = None,
    ) -> str:
        """Re-transcribe only the failed segments in an existing short-ASR output.

        Re-splits the audio identically and retranscribes failed chunks.
        Returns md_path, or raises on total/partial failure.
        """
        failed_indices = self.find_failed_segments(md_path)
        if not failed_indices:
            logger.info("[ASR-REPAIR] 没有发现识别失败的分段: %s", md_path)
            return md_path

        if not os.path.isfile(audio_path):
            raise RuntimeError(f"音频文件不存在，无法修复: {audio_path}")

        # Re-split audio identically
        actual_path = audio_path
        if not _is_remote(audio_path):
            actual_path = self._ensure_upload_format(audio_path)
        _, duration = self._should_use_short_asr(actual_path)
        chunks = self._split_audio(actual_path, duration=duration)

        sys_prompt = self._build_system_prompt(hotwords, prompt_template)
        total = len(failed_indices)
        logger.info("[ASR-REPAIR] 需要修复 %d 个分段", total)
        self._report(0, total, f"修复 {total} 个失败分段...")

        results: dict[int, str] = {}  # 1-based index → text
        still_failed: list[int] = []

        for order, seg_idx in enumerate(failed_indices):
            self._check_cancelled()
            chunk_idx = seg_idx - 1  # 0-based
            if chunk_idx < 0 or chunk_idx >= len(chunks):
                still_failed.append(seg_idx)
                continue

            chunk = chunks[chunk_idx]
            self._report(order + 1, total, f"识别分段 {seg_idx} ({order + 1}/{total})")
            try:
                text = self.llm.transcribe_short_audio(
                    audio_path=chunk.path,
                    system_prompt=sys_prompt,
                    model=self.cfg.models.asr_short_model,
                )
                text = strip_md_fence(text)
                if not text or not text.strip():
                    text = "（无文本）"
                results[seg_idx] = text
                self._report_content(text, f"修复识别 — 分段 {seg_idx}")
            except CancelledError:
                raise
            except Exception as e:
                logger.error("[ASR-REPAIR] 分段 %d 失败: %s", seg_idx, e)
                still_failed.append(seg_idx)

        if not results:
            raise RuntimeError(f"音频修复全部 {total} 个分段失败")

        # Replace failure markers in the MD
        content = Path(md_path).read_text(encoding="utf-8")
        for seg_idx, text in results.items():
            pattern = re.compile(
                r"（分段\s+" + str(seg_idx) + r"\s+(?:识别失败|未完成)(?::.*?)?）",
            )
            content = pattern.sub(text, content, count=1)

        Path(md_path).write_text(content, encoding="utf-8")
        logger.info(
            "[ASR-REPAIR] 修复完成: %d/%d 分段成功, %d 分段仍失败 -> %s",
            len(results), total, len(still_failed), md_path,
        )
        if still_failed:
            raise RuntimeError(
                f"音频修复后仍有 {len(still_failed)} 个分段失败: {still_failed}: {md_path}"
            )
        return md_path

    def _process_google_long_audio(
        self,
        audio_path: str,
        hotwords: Optional[list[str]] = None,
        output_path: str = None,
        prompt_template: str = None,
        resume: bool = False,
    ) -> str:
        """Google 模式走 Files API，并按录课友好的长片段切分后合并。"""
        if not self.cfg.google_api.api_key:
            raise ValueError("未配置 Google API Key。请在谷歌模式中填入 Google AI Studio API Key")
        if _is_remote(audio_path):
            raise ValueError("Google 模式当前只支持本地音频文件上传到 Files API，不支持远程音频 URL")

        stem = Path(audio_path).stem
        if output_path is None:
            output_path = os.path.join(ensure_dir(self.cfg.paths.output_dir), f"{stem}_录音识别.md")

        self._report(1, 4, f"Google 长音频模式: {self.cfg.google_api.audio_model}")
        base_prompt = self._build_system_prompt(hotwords, prompt_template)
        duration = None
        try:
            duration = self._get_cached_duration(audio_path)
        except Exception as exc:
            logger.warning("[ASR] Google 长音频时长探测失败，跳过长度型假成功校验: %s", exc)
        if duration and duration >= _GOOGLE_WEAK_AUDIO_MIN_DURATION:
            try:
                stats = measure_audio_signal(audio_path, cancel_event=self.reporter.cancel_event)
            except Exception as exc:
                logger.warning("[ASR] Google 长音频响度探测失败，继续交给模型与正文校验: %s", exc)
            else:
                invalid_signal = google_audio_signal_invalid_reason(stats, duration=duration)
                if invalid_signal:
                    raise RuntimeError(f"Google 长音频输入不可用: {invalid_signal}")

        chunks = self._split_google_audio(audio_path, duration=duration)
        if not chunks:
            raise RuntimeError("Google 长音频分割失败：没有可识别片段")

        global_checkpoint = Checkpoint(
            task_type="audio",
            source_path=audio_path,
            output_path=output_path,
            total_items=len(chunks),
            extra={
                "provider": "google",
                "hotwords": list(hotwords or []),
                "prompt_template": prompt_template,
            },
        )

        model_candidates = self._google_audio_model_candidates()
        last_false_success_reason = None
        md_lines = []
        segment_texts: list[tuple[AudioChunk, str, str]] = []

        for model_pos, active_model in enumerate(model_candidates):
            checkpoint_path, checkpoint_meta = self._google_audio_checkpoint_path(
                audio_path=audio_path,
                output_path=output_path,
                base_prompt=base_prompt,
                chunks=chunks,
                audio_model=active_model,
            )
            segment_text_by_index = self._load_google_audio_checkpoint(checkpoint_path, checkpoint_meta, chunks)
            global_checkpoint.replace_completed({index - 1 for index in segment_text_by_index})
            self.checkpoint_mgr.save(global_checkpoint)
            self._report(
                2,
                4,
                f"上传并请求 Gemini 识别 {len(chunks)} 个音频片段... 模型={active_model}",
            )

            false_success_reason = None
            try:
                for idx, chunk in enumerate(chunks, start=1):
                    self._check_cancelled()
                    t1 = _ms_ts(int(chunk.logical_start * 1000))
                    t2 = _ms_ts(int(chunk.logical_end * 1000))
                    if idx in segment_text_by_index:
                        self._report(2, 4, f"复用 Google 已完成片段 {idx}/{len(chunks)} ({t1}~{t2})...")
                        continue

                    segment_duration = max(0.0, chunk.logical_end - chunk.logical_start)
                    segment_prompt = self._build_google_segment_prompt(base_prompt, idx, chunk, len(chunks))
                    self._report(2, 4, f"Google 识别片段 {idx}/{len(chunks)} ({t1}~{t2})...")
                    text = self.llm.transcribe_long_audio(
                        audio_path=chunk.path,
                        system_prompt=segment_prompt,
                        model=active_model,
                        text_validator=lambda value, dur=segment_duration, terms=hotwords: google_audio_transcript_invalid_reason(
                            self._strip_model_segment_marker(strip_md_fence(value)),
                            duration=dur,
                            expected_terms=terms,
                        ),
                    )
                    text = strip_md_fence(text).strip()
                    false_success_reason = google_audio_transcript_invalid_reason(
                        self._strip_model_segment_marker(text),
                        duration=segment_duration,
                        expected_terms=hotwords,
                    )
                    if false_success_reason:
                        break

                    model_used = active_model
                    last_successful_model = getattr(self.llm, "last_successful_model", None)
                    if callable(last_successful_model):
                        reported_model = last_successful_model("audio")
                        if isinstance(reported_model, str) and reported_model.strip():
                            model_used = reported_model.strip()
                    segment_text_by_index[idx] = (chunk, text, model_used)
                    self._write_google_audio_checkpoint(checkpoint_path, checkpoint_meta, segment_text_by_index)
                    global_checkpoint.mark_completed(idx - 1)
                    self.checkpoint_mgr.save(global_checkpoint)
            except Exception:
                self.checkpoint_mgr.save(global_checkpoint)
                raise

            if false_success_reason is None:
                segment_texts = [segment_text_by_index[idx] for idx in range(1, len(chunks) + 1)]
                merged_body = "\n\n".join(
                    self._strip_model_segment_marker(text)
                    for _, text, _model in segment_texts
                )
                false_success_reason = google_audio_transcript_invalid_reason(
                    merged_body,
                    duration=duration,
                    expected_terms=hotwords,
                )

            if false_success_reason:
                last_false_success_reason = false_success_reason
                try:
                    checkpoint_path.unlink(missing_ok=True)
                except OSError as exc:
                    logger.warning("[ASR] Google invalid transcript checkpoint cleanup failed: %s", exc)
                global_checkpoint.replace_completed(set())
                self.checkpoint_mgr.save(global_checkpoint)
                if model_pos + 1 < len(model_candidates):
                    next_model = model_candidates[model_pos + 1]
                    logger.warning(
                        "[ASR] Google 模型疑似假成功，切换下一音频模型: %s -> %s (%s)",
                        active_model,
                        next_model,
                        false_success_reason,
                    )
                    continue
                raise RuntimeError(f"Google 长音频识别疑似假成功: {false_success_reason}")

            md_lines = [f"<!-- meta:audio title={stem} -->\n"]
            md_lines.append(f"> Provider: Google Gemini SDK\n")
            md_lines.append(f"> 模型优先级起点: {self.cfg.google_api.audio_model}\n")
            actual_models = list(dict.fromkeys(model for _, _, model in segment_texts if model))
            if actual_models:
                md_lines.append(f"> 实际使用模型: {', '.join(actual_models)}\n")
            md_lines.append(
                f"> Google 切片: 逻辑 {self.cfg.google_api.audio_chunk_seconds}s，"
                f"上下文重叠 {self.cfg.google_api.audio_overlap_seconds}s\n"
            )
            if hotwords:
                md_lines.append(f"> 热词: {', '.join(hotwords)}\n")
            md_lines.append("")
            segment_index = 1
            for chunk, text, _model_used in segment_texts:
                fine_segments = self._parse_model_fine_segments(text)
                if fine_segments:
                    for time_range, body in fine_segments:
                        if time_range:
                            md_lines.extend([f"<!-- meta:segment index={segment_index} time={time_range} -->\n", body, ""])
                        else:
                            md_lines.extend([f"<!-- meta:segment index={segment_index} -->\n", body, ""])
                        segment_index += 1
                    continue
                t1 = _ms_ts(int(chunk.logical_start * 1000))
                t2 = _ms_ts(int(chunk.logical_end * 1000))
                body = self._strip_model_segment_marker(text)
                md_lines.extend([f"<!-- meta:segment index={segment_index} time={t1}~{t2} -->\n", body, ""])
                segment_index += 1
            break

        if not md_lines:
            raise RuntimeError(f"Google 长音频识别疑似假成功: {last_false_success_reason or '所有候选模型均未产出有效转写'}")

        self._report(3, 4, "写入 Markdown...")
        ensure_dir(os.path.dirname(output_path))
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines).strip() + "\n")
        self._report_content("\n\n".join(text for _, text, _model in segment_texts), "Google 长音频识别完成")
        self._report(4, 4, f"完成: {output_path}")
        self.checkpoint_mgr.remove("audio", audio_path)
        return output_path

    def _google_audio_checkpoint_path(
        self,
        audio_path: str,
        output_path: str,
        base_prompt: str,
        chunks: list[AudioChunk],
        audio_model: str | None = None,
    ) -> tuple[Path, dict]:
        chunk_meta = [
            {
                "index": idx,
                "actual_start": round(chunk.actual_start, 3),
                "actual_end": round(chunk.actual_end, 3),
                "logical_start": round(chunk.logical_start, 3),
                "logical_end": round(chunk.logical_end, 3),
            }
            for idx, chunk in enumerate(chunks, start=1)
        ]
        try:
            source_stat = Path(audio_path).stat()
            source_size = int(source_stat.st_size)
            source_mtime_ns = int(source_stat.st_mtime_ns)
        except OSError:
            source_size = None
            source_mtime_ns = None

        meta = {
            "version": 1,
            "source": str(Path(audio_path).resolve()),
            "source_size": source_size,
            "source_mtime_ns": source_mtime_ns,
            "output": str(Path(output_path).resolve()),
            "audio_model": audio_model or self.cfg.google_api.audio_model,
            "chunk_seconds": int(self.cfg.google_api.audio_chunk_seconds),
            "overlap_seconds": int(self.cfg.google_api.audio_overlap_seconds),
            "prompt_hash": hashlib.sha256(base_prompt.encode("utf-8")).hexdigest(),
            "chunks": chunk_meta,
        }
        digest = hashlib.sha256(
            json.dumps(meta, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:20]
        safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(output_path).stem).strip("._")
        if not safe_stem:
            safe_stem = "google_audio"
        checkpoint_dir = Path(ensure_dir(os.path.join(self.cfg.paths.temp_dir, "google_audio_checkpoints")))
        return checkpoint_dir / f"{safe_stem[:80]}.{digest}.json", meta

    def _google_audio_model_candidates(self) -> list[str]:
        from OCRLLM.core import model_catalog
        from OCRLLM.core.providers.google_provider import prioritize_google_audio_models

        primary = (self.cfg.google_api.audio_model or "").strip()
        chain = prioritize_google_audio_models(
            self.cfg.google_api.audio_model_queue or model_catalog.google_free_audio_chain()
        )
        candidates = []
        for model in [primary, *chain]:
            model = (model or "").strip()
            if model and model not in candidates:
                candidates.append(model)
        if not candidates:
            raise RuntimeError("Google 音频识别没有可用模型，请在设置中选择 Google 音频模型")
        return candidates

    def _load_google_audio_checkpoint(
        self,
        checkpoint_path: Path,
        expected_meta: dict,
        chunks: list[AudioChunk],
    ) -> dict[int, tuple[AudioChunk, str, str]]:
        if not checkpoint_path.exists():
            return {}
        try:
            payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("[ASR] Google 断点缓存读取失败，忽略旧缓存: %s", exc)
            return {}
        if payload.get("metadata") != expected_meta:
            return {}

        cached: dict[int, tuple[AudioChunk, str, str]] = {}
        segments = payload.get("segments")
        if not isinstance(segments, dict):
            return cached
        for raw_index, item in segments.items():
            try:
                index = int(raw_index)
            except (TypeError, ValueError):
                continue
            if index < 1 or index > len(chunks) or not isinstance(item, dict):
                continue
            chunk = chunks[index - 1]
            if not self._google_checkpoint_segment_matches(item, chunk):
                continue
            text = str(item.get("text") or "").strip()
            model = str(item.get("model") or self.cfg.google_api.audio_model).strip()
            duration = max(0.0, chunk.logical_end - chunk.logical_start)
            try:
                validate_google_audio_transcript(
                    self._strip_model_segment_marker(text),
                    duration=duration,
                )
            except RuntimeError:
                continue
            cached[index] = (chunk, text, model)
        return cached

    @staticmethod
    def _google_checkpoint_segment_matches(item: dict, chunk: AudioChunk) -> bool:
        def same_time(key: str, expected: float) -> bool:
            try:
                return abs(float(item.get(key)) - round(expected, 3)) < 0.001
            except (TypeError, ValueError):
                return False

        return (
            same_time("actual_start", chunk.actual_start)
            and same_time("actual_end", chunk.actual_end)
            and same_time("logical_start", chunk.logical_start)
            and same_time("logical_end", chunk.logical_end)
        )

    def _write_google_audio_checkpoint(
        self,
        checkpoint_path: Path,
        metadata: dict,
        segments: dict[int, tuple[AudioChunk, str, str]],
    ) -> None:
        payload = {
            "metadata": metadata,
            "segments": {
                str(index): {
                    "actual_start": round(chunk.actual_start, 3),
                    "actual_end": round(chunk.actual_end, 3),
                    "logical_start": round(chunk.logical_start, 3),
                    "logical_end": round(chunk.logical_end, 3),
                    "model": model,
                    "text": text,
                }
                for index, (chunk, text, model) in sorted(segments.items())
            },
        }
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = checkpoint_path.with_suffix(checkpoint_path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp_path, checkpoint_path)

    def _build_google_segment_prompt(
        self,
        base_prompt: str,
        index: int,
        chunk: AudioChunk,
        total: int,
    ) -> str:
        t1 = _ms_ts(int(chunk.logical_start * 1000))
        t2 = _ms_ts(int(chunk.logical_end * 1000))
        marker = f"<!-- meta:segment index={index} time={t1}~{t2} -->"
        return (
            f"{base_prompt}\n\n"
            "Google 录课音频分段格式要求：\n"
            f"- 这是第 {index}/{total} 个音频片段，逻辑时间范围为 {t1}~{t2}。\n"
            "- 请在这一片段内部标注更细的时间戳。优先每 1~3 分钟、话题切换、长停顿或板书切换处新开一段。\n"
            "- 每个小段前必须单独写一行 HTML 注释，格式为：<!-- meta:segment index=序号 time=开始时间~结束时间 -->。\n"
            f"- 如果无法可靠细分，只输出一个小段，第一行写成：{marker}\n"
            "- 时间必须使用整段课程的绝对时间，不要使用片段内相对时间。\n"
            "- meta 注释之后只写对应小段的逐字转写正文。\n"
            "- 不要省略 HTML 注释，不要把 meta 注释放进代码块，不要输出 Markdown 围栏。\n"
            "- 如果音频开头或结尾听到与相邻片段重复的上下文，只保留属于上述逻辑时间范围的内容。"
        )

    @staticmethod
    def _strip_model_segment_marker(text: str) -> str:
        lines = text.strip().splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)
        inline_marker = re.compile(r"<!--\s*meta:segment\b.*?-->\s*", flags=re.IGNORECASE)
        lines = [
            inline_marker.sub("", line).rstrip()
            for line in lines
            if not re.match(r"^<!--\s*meta:segment\b.*-->\s*$", line.strip(), flags=re.IGNORECASE)
        ]
        return "\n".join(lines).strip()

    @staticmethod
    def _parse_model_fine_segments(text: str) -> list[tuple[str | None, str]]:
        segments: list[tuple[str | None, str]] = []
        current_time: str | None = None
        current_lines: list[str] = []
        saw_marker = False
        saw_body_before_marker = False

        def flush():
            nonlocal current_time, current_lines
            body = "\n".join(current_lines).strip()
            if body:
                segments.append((current_time, body))
            current_time = None
            current_lines = []

        for line in text.strip().splitlines():
            marker_match = _MODEL_SEGMENT_RE.match(line.strip())
            if marker_match:
                if not saw_marker and any(part.strip() for part in current_lines):
                    saw_body_before_marker = True
                saw_marker = True
                flush()
                time_match = _MODEL_SEGMENT_TIME_RE.search(marker_match.group("attrs") or "")
                current_time = time_match.group("time") if time_match else None
                continue
            current_lines.append(line)
        flush()
        return segments if saw_marker and segments and not saw_body_before_marker else []

    @staticmethod
    def resume_options_from_checkpoint(checkpoint: Checkpoint) -> dict:
        extra = checkpoint.extra or {}
        return {
            "audio_path": checkpoint.source_path,
            "output_path": checkpoint.output_path,
            "hotwords": extra.get("hotwords") or None,
            "prompt_template": extra.get("prompt_template") or None,
            "resume": True,
        }

    def _short_asr(self, audio_path: str, hotwords, output_path: str,
                   prompt_template: str = None, duration: float = None,
                   fallback_mode: bool = False) -> str:
        stem = Path(audio_path).stem
        chunks = self._split_audio(audio_path, duration=duration, fallback_mode=fallback_mode)
        sys_prompt = self._build_system_prompt(hotwords, prompt_template)

        md_lines = [f"<!-- meta:audio title={stem} -->\n"]
        if hotwords:
            md_lines.append(f"> 热词: {', '.join(hotwords)}\n")
        md_lines.append(f"> 模型: {self.cfg.models.asr_short_model}\n")
        if fallback_mode:
            md_lines.append(
                f"> 回退切片: 逻辑 {self.cfg.processing.asr_fallback_chunk_seconds}s，"
                f"上下文 {self.cfg.processing.asr_fallback_context_seconds}s\n"
            )

        workers = resolve_workers(
            self.cfg.concurrency.audio_asr_parallel_requests,
            len(chunks),
            hard_cap=8,
        )
        total = len(chunks) + 1

        def _transcribe_one(idx: int, chunk: AudioChunk) -> tuple[int, str, str, str]:
            t1 = _ms_ts(int(chunk.logical_start * 1000))
            t2 = _ms_ts(int(chunk.logical_end * 1000))
            try:
                text = self.llm.transcribe_short_audio(
                    audio_path=chunk.path,
                    system_prompt=sys_prompt,
                    model=self.cfg.models.asr_short_model,
                )
                text = strip_md_fence(text)
            except CancelledError:
                raise
            except Exception as e:
                logger.error("[ASR] 分段 %d 失败: %s", idx + 1, e)
                text = f"（分段 {idx + 1} 识别失败: {e}）"
            return idx, t1, t2, text or "（无文本）"

        ordered = [None] * len(chunks)
        executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="audio-asr")
        future_map = {}
        try:
            for idx, chunk in enumerate(chunks):
                self._check_cancelled()
                future = executor.submit(_transcribe_one, idx, chunk)
                future_map[future] = idx

            done = 0
            for future in self._iter_completed_futures(set(future_map)):
                future_map.pop(future, None)
                idx, t1, t2, text = future.result()
                ordered[idx] = (t1, t2, text)
                done += 1
                self._report(done, total, f"识别分段 {done}/{len(chunks)}...")
                self._report_content(text, f"语音识别 — [{t1} ~ {t2}]")
        finally:
            self._cancel_futures(future_map)
            executor.shutdown(wait=False, cancel_futures=True)

        for idx, entry in enumerate(ordered):
            if entry is None:
                chunk = chunks[idx]
                t1 = _ms_ts(int(chunk.logical_start * 1000))
                t2 = _ms_ts(int(chunk.logical_end * 1000))
                md_lines.extend([f"<!-- meta:segment index={idx + 1} time={t1}~{t2} -->\n", f"（分段 {idx + 1} 未完成）", ""])
            else:
                t1, t2, text = entry
                md_lines.extend([f"<!-- meta:segment index={idx + 1} time={t1}~{t2} -->\n", text, ""])

        ensure_dir(os.path.dirname(output_path))
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines).strip() + "\n")

        try:
            total_duration = sum(chunk.logical_end - chunk.logical_start for chunk in chunks)
            est_cost = total_duration * 0.22 / 1000
            logger.info(
                f"[ASR] 短音频识别完成: {stem}, {len(chunks)} 个分段, 总时长 {total_duration:.1f}s, "
                f"按官网价格 (0.22 元/千秒) 预计费用约 {est_cost:.3f} 元")
        except Exception as e:
            logger.warning(f"[ASR] 无法计算短音频总时长: {e}")
        return output_path

    def _ensure_upload_format(self, audio_path: str) -> str:
        ext = Path(audio_path).suffix.lower()
        if ext in _DASHSCOPE_NATIVE_FORMATS:
            return audio_path

        logger.info("[ASR] 格式 %s 不在 DashScope 原生支持列表，转为 MP3", ext)
        ffmpeg = get_ffmpeg()
        temp_dir = ensure_dir(os.path.join(self.cfg.paths.temp_dir, "audio_converted"))
        out = os.path.join(temp_dir, Path(audio_path).stem + ".mp3")
        if os.path.exists(out):
            return out

        self._report(0, 1, f"转换音频 {ext} → MP3...")
        cmd = [
            ffmpeg,
            "-i",
            audio_path,
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-ab",
            "32k",
            "-acodec",
            "libmp3lame",
            "-y",
            out,
        ]
        result = run_subprocess_cancellable(
            cmd, cancel_event=self.reporter.cancel_event, timeout=600,
        )
        if result.returncode != 0:
            stderr = (result.stderr if isinstance(result.stderr, str)
                      else (result.stderr or b"").decode("utf-8", errors="replace"))
            raise RuntimeError(f"ffmpeg 转换失败: {stderr[:500]}")
        return out

    def _split_google_audio(self, audio_path: str, duration: float = None) -> list[AudioChunk]:
        dur = duration if duration is not None else self._get_cached_duration(audio_path)
        if dur <= 0:
            raise RuntimeError(f"音频时长无效，无法进行 Google 分片: {audio_path}")

        chunk_seconds = max(1, int(self.cfg.google_api.audio_chunk_seconds))
        overlap_seconds = max(0, int(self.cfg.google_api.audio_overlap_seconds))
        if overlap_seconds >= chunk_seconds:
            overlap_seconds = max(0, chunk_seconds - 1)

        windows = build_google_audio_windows(dur, chunk_seconds, overlap_seconds)
        if not windows:
            return []

        if len(windows) == 1 and windows[0].actual_start <= 0.001 and abs(windows[0].actual_end - dur) <= 0.001:
            window = windows[0]
            return [AudioChunk(
                path=audio_path,
                actual_start=window.actual_start,
                actual_end=window.actual_end,
                logical_start=window.logical_start,
                logical_end=window.logical_end,
            )]

        ffmpeg = get_ffmpeg()
        chunk_dir = ensure_dir(os.path.join(self.cfg.paths.temp_dir, "google_audio_chunks", Path(audio_path).stem))
        chunks = [None] * len(windows)
        workers = resolve_workers(self.cfg.concurrency.audio_split_workers, len(windows), hard_cap=6)

        def _split_one(idx: int, window: AudioWindow) -> tuple[int, AudioChunk]:
            out = os.path.join(chunk_dir, f"google_part{idx + 1:03d}.mp3")
            cmd = [
                ffmpeg,
                "-ss",
                f"{window.actual_start:.3f}",
                "-i",
                audio_path,
                "-t",
                f"{window.actual_end - window.actual_start:.3f}",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-ab",
                "64k",
                "-acodec",
                "libmp3lame",
                "-y",
                out,
            ]
            run_subprocess_cancellable(
                cmd,
                cancel_event=self.reporter.cancel_event,
                timeout=max(600, int(window.actual_end - window.actual_start) + 300),
                check=True,
            )
            return idx, AudioChunk(
                path=out,
                actual_start=window.actual_start,
                actual_end=window.actual_end,
                logical_start=window.logical_start,
                logical_end=window.logical_end,
            )

        executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="google-audio-split")
        future_map = {}
        try:
            for idx, window in enumerate(windows):
                self._check_cancelled()
                future = executor.submit(_split_one, idx, window)
                future_map[future] = idx

            for future in self._iter_completed_futures(set(future_map)):
                future_map.pop(future, None)
                idx, chunk = future.result()
                chunks[idx] = chunk
        finally:
            self._cancel_futures(future_map)
            executor.shutdown(wait=False, cancel_futures=True)

        return [chunk for chunk in chunks if chunk is not None]

    def _should_use_short_asr(self, audio_path: str) -> tuple[bool, float]:
        """判断是否应使用短音频 ASR 模型。

        Returns:
            (should_use_short, duration_seconds)
        """
        dur = self._get_cached_duration(audio_path)
        size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        return dur <= self.cfg.processing.asr_short_chunk_seconds and size_mb <= 9.5, dur

    def _split_audio(self, audio_path: str, duration: float = None, fallback_mode: bool = False) -> list[AudioChunk]:
        max_chunk = (
            self.cfg.processing.asr_fallback_chunk_seconds
            if fallback_mode else self.cfg.processing.asr_short_chunk_seconds
        )
        context_seconds = self.cfg.processing.asr_fallback_context_seconds if fallback_mode else 0
        dur = duration if duration is not None else self._get_cached_duration(audio_path)
        size_mb = os.path.getsize(audio_path) / (1024 * 1024)

        if not fallback_mode and dur <= max_chunk and size_mb <= 9.5:
            return [AudioChunk(audio_path, 0.0, dur, 0.0, dur)]

        ffmpeg = get_ffmpeg()
        chunk_dir = ensure_dir(os.path.join(self.cfg.paths.temp_dir, "audio_chunks", Path(audio_path).stem))
        windows = (
            build_fallback_audio_windows(dur, max_chunk, context_seconds)
            if fallback_mode
            else [
                AudioWindow(
                    actual_start=idx * max_chunk,
                    actual_end=min((idx + 1) * max_chunk, dur),
                    logical_start=idx * max_chunk,
                    logical_end=min((idx + 1) * max_chunk, dur),
                )
                for idx in range(int(math.ceil(dur / max_chunk)))
            ]
        )
        chunk_count = len(windows)
        chunks = [None] * chunk_count
        workers = resolve_workers(self.cfg.concurrency.audio_split_workers, chunk_count, hard_cap=8)

        def _split_one(idx: int, window: AudioWindow) -> tuple[int, AudioChunk]:
            out = os.path.join(chunk_dir, f"part{idx + 1:03d}.mp3")
            cmd = [
                ffmpeg,
                "-ss",
                f"{window.actual_start:.3f}",
                "-i",
                audio_path,
                "-t",
                f"{window.actual_end - window.actual_start:.3f}",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-ab",
                "32k",
                "-acodec",
                "libmp3lame",
                "-y",
                out,
            ]
            run_subprocess_cancellable(
                cmd, cancel_event=self.reporter.cancel_event,
                timeout=600, check=True,
            )
            return idx, AudioChunk(
                path=out,
                actual_start=window.actual_start,
                actual_end=window.actual_end,
                logical_start=window.logical_start,
                logical_end=window.logical_end,
            )

        executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="audio-split")
        future_map = {}
        try:
            for idx, window in enumerate(windows):
                self._check_cancelled()
                future = executor.submit(_split_one, idx, window)
                future_map[future] = idx

            for future in self._iter_completed_futures(set(future_map)):
                future_map.pop(future, None)
                idx, chunk = future.result()
                chunks[idx] = chunk
        finally:
            self._cancel_futures(future_map)
            executor.shutdown(wait=False, cancel_futures=True)
        # 过滤掉分割失败的 None 项
        return [c for c in chunks if c is not None]

    def _build_system_prompt(self, hotwords, prompt_template: str = None) -> str:
        instruction = ""
        if hotwords:
            deduped = list(dict.fromkeys(w.strip() for w in hotwords if w.strip()))
            if deduped:
                instruction = "以下术语为课程热词。如果音频中出现同音或近音内容，优先采用这些写法：\n" + "、".join(deduped)
        template = prompt_template or prompts.AUDIO_TRANSCRIBE
        return template.format(hotwords_instruction=instruction).strip()

    def _submit_headers(self, file_url: str = "") -> dict:
        headers = {
            "Authorization": f"Bearer {self.cfg.api.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        if _needs_dashscope_oss_resolver(file_url):
            headers["X-DashScope-OssResourceResolve"] = "enable"
        return headers

    def _poll_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.cfg.api.api_key}"}

    def _upload_file(self, file_path: str) -> str:
        if _uses_dashscope_oss_upload(self.cfg.models.asr_model):
            return self._upload_oss_file(file_path)
        return self._upload_file_api_file(file_path)

    def _upload_oss_file(self, file_path: str) -> str:
        if not self.cfg.api.api_key:
            raise RuntimeError("DashScope OSS 上传失败: 未配置 API Key")
        try:
            from dashscope.utils.oss_utils import OssUtils
        except ImportError as e:
            raise RuntimeError("DashScope OSS 上传失败: 缺少 dashscope SDK") from e

        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        logger.info(
            "[ASR] OSS 上传文件: %s (%.1fMB)",
            Path(file_path).name,
            size_mb,
        )
        file_url, _upload_certificate = OssUtils.upload(
            model=self.cfg.models.asr_model,
            file_path=file_path,
            api_key=self.cfg.api.api_key,
        )
        if not file_url or not str(file_url).startswith("oss://"):
            raise RuntimeError(f"DashScope OSS 上传未返回 oss:// URL: {file_url}")
        logger.info("[ASR] OSS 上传完成: scheme=oss, model=%s", self.cfg.models.asr_model)
        return str(file_url)

    def _upload_file_api_file(self, file_path: str) -> str:
        headers = {"Authorization": f"Bearer {self.cfg.api.api_key}"}
        ext = Path(file_path).suffix.lower()
        content_type = {
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".flac": "audio/flac",
            ".opus": "audio/opus",
            ".aac": "audio/aac",
            ".amr": "audio/amr",
            ".wma": "audio/x-ms-wma",
        }.get(ext, "application/octet-stream")

        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        upload_timeout = max(120, int(size_mb * 10) + 60)

        def _do():
            session = self._get_http_session()
            with open(file_path, "rb") as f:
                response = session.post(
                    self._files_url,
                    headers=headers,
                    files={"files": (Path(file_path).name, f, content_type)},
                    data={"purpose": "file-extract"},
                    timeout=upload_timeout,
                )
            response.raise_for_status()
            return response.json()

        logger.info("[ASR] 上传文件: %s (%.1fMB, timeout=%ds)", Path(file_path).name, size_mb, upload_timeout)
        data = _retry_on_ssl(_do, 6, base_delay=15, sleep_fn=self._sleep)
        file_id = data.get("data", {}).get("uploaded_files", [{}])[0].get("file_id")
        if not file_id:
            raise RuntimeError(f"上传失败: {json.dumps(data, ensure_ascii=False)[:500]}")

        def _info():
            response = self._get_http_session().get(f"{self._files_url}/{file_id}", headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()

        info = _retry_on_ssl(_info, 4, sleep_fn=self._sleep)
        data = info.get("data", {})
        url = data.get("url") or data.get("file_url") or data.get("oss_url") or data.get("download_url")
        if not url:
            raise RuntimeError(f"未获取文件 URL: {json.dumps(info, ensure_ascii=False)[:500]}")
        return url

    def _submit_task(self, file_url: str, hotwords=None) -> str:
        model_name = self.cfg.models.asr_model
        if _uses_single_file_url(model_name):
            audio_input = {"file_url": file_url}
        else:
            audio_input = {"file_urls": [file_url]}
        submit_headers = self._submit_headers(file_url)
        logger.info(
            "[ASR] 提交 filetrans: model=%s, input=%s, oss_resolver=%s",
            model_name,
            "file_url" if "file_url" in audio_input else "file_urls",
            "X-DashScope-OssResourceResolve" in submit_headers,
        )
        payload = {
            "model": model_name,
            "input": audio_input,
            "parameters": {"channel_id": [0], "enable_itn": False, "enable_words": True},
        }
        corpus = self._build_corpus(hotwords)
        if corpus:
            payload["parameters"]["corpus"] = {"text": corpus}

        response = _retry_on_ssl(
            lambda: self._get_http_session().post(
                self._submit_url,
                headers=submit_headers,
                json=payload,
                timeout=30,
            ),
            4,
            sleep_fn=self._sleep,
        )
        if response.status_code != 200:
            raise RuntimeError(f"ASR 提交失败: HTTP {response.status_code}\n{response.text}")
        response_data = response.json()
        task_id = response_data.get("output", {}).get("task_id")
        if not task_id:
            raise RuntimeError(f"长音频异步接口未返回 task_id: {response_data}")
        return task_id

    def _wait_result(self, task_id: str, poll_interval: float, max_wait: float) -> dict:
        url = self._task_url_template.format(task_id=task_id)
        headers = self._poll_headers()
        start = time.time()
        consecutive_errors = 0
        last_report_bucket = -1

        while time.time() - start < max_wait:
            self._check_cancelled()
            try:
                response = self._get_http_session().get(url, headers=headers, timeout=30)
            except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
                consecutive_errors += 1
                if consecutive_errors > 10:
                    raise RuntimeError(f"ASR 轮询连续 {consecutive_errors} 次网络错误: {e}") from e
                delay = poll_interval * min(consecutive_errors, 6)
                logger.warning("[ASR] 网络错误 (第 %d 次): %s, %.0fs 后重试", consecutive_errors, e, delay)
                self._sleep(delay)
                continue

            if response.status_code in (401, 403):
                raise RuntimeError(f"ASR 认证失败 (HTTP {response.status_code}): {response.text[:500]}")
            if response.status_code == 404:
                raise RuntimeError(f"ASR 任务不存在 (task_id={task_id}): {response.text[:300]}")
            if 400 <= response.status_code < 500:
                raise RuntimeError(f"ASR 请求错误 (HTTP {response.status_code}): {response.text[:500]}")
            if response.status_code >= 500:
                consecutive_errors += 1
                if consecutive_errors > 8:
                    raise RuntimeError(f"ASR 服务端连续 {consecutive_errors} 次错误 (HTTP {response.status_code})")
                delay = poll_interval * min(consecutive_errors, 6)
                logger.warning(
                    "[ASR] 服务端错误 HTTP %d (第 %d 次), %.0fs 后重试",
                    response.status_code,
                    consecutive_errors,
                    delay,
                )
                self._sleep(delay)
                continue

            consecutive_errors = 0
            data = response.json()
            status = data.get("output", {}).get("task_status", "")
            elapsed = time.time() - start
            report_bucket = int(elapsed // 30)

            if status == "SUCCEEDED":
                self._raise_on_failed_success_payload(data)
                logger.info("[ASR] 任务完成，耗时 %.1fs", elapsed)
                return data
            if status == "FAILED":
                code = data.get("output", {}).get("code", "")
                msg = data.get("output", {}).get("message", "未知错误")
                if code and "NO_VALID_FRAGMENT" in str(code):
                    logger.warning("[ASR] 文件转写未检测到有效语音 (NO_VALID_FRAGMENT)，耗时 %.1fs", elapsed)
                    raise ASRNoValidFragmentError(f"DashScope filetrans 返回 {code}: {msg}")
                if code:
                    msg = f"{code}: {msg}"
                logger.error("[ASR] 任务失败: %s", msg)
                raise RuntimeError(f"ASR 失败: {msg}")
            if status == "SUCCESS_WITH_NO_VALID_FRAGMENT":
                logger.warning("[ASR] 文件转写未检测到有效语音，耗时 %.1fs", elapsed)
                raise ASRNoValidFragmentError("DashScope filetrans 返回 SUCCESS_WITH_NO_VALID_FRAGMENT")
            if status == "UNKNOWN":
                logger.error("[ASR] 异常状态: UNKNOWN, response=%s", json.dumps(data, ensure_ascii=False)[:500])
                raise RuntimeError("ASR 状态异常: UNKNOWN")
            if status in ("PENDING", "RUNNING") and report_bucket > last_report_bucket:
                last_report_bucket = report_bucket
                wait_text = f"{int(elapsed)}s" if elapsed < 120 else f"{elapsed/60:.1f}min"
                logger.info("[ASR] 任务状态: %s, 已等待 %s", status, wait_text)
                self._report(4, 5, f"等待识别完成... 状态={status}, 已等待 {wait_text}")
            self._sleep(poll_interval)

        raise TimeoutError(f"ASR 超时 ({max_wait}s)")

    @staticmethod
    def _raise_on_failed_success_payload(data: dict) -> None:
        output = data.get("output", {}) if isinstance(data, dict) else {}
        items: list[dict] = []
        result = output.get("result")
        if isinstance(result, dict):
            items.append(result)
        results = output.get("results")
        if isinstance(results, list):
            items.extend(item for item in results if isinstance(item, dict))

        for item in items:
            status = str(item.get("subtask_status") or "").upper()
            code = item.get("code")
            message = item.get("message")
            if status == "FAILED" or code:
                detail = ": ".join(str(part) for part in (code, message) if part)
                raise RuntimeError(f"ASR 子任务失败: {detail or json.dumps(item, ensure_ascii=False)[:500]}")

        task_metrics = output.get("task_metrics")
        if isinstance(task_metrics, dict) and int(task_metrics.get("FAILED") or 0) > 0:
            raise RuntimeError(f"ASR 子任务失败: {json.dumps(task_metrics, ensure_ascii=False)}")

    def _result_to_md(self, result: dict, title: str) -> str:
        transcripts = self._extract_transcripts(result)
        if not transcripts:
            logger.error("[ASR] 任务成功但无转写结果: %s, result=%s",
                        title, json.dumps(result, ensure_ascii=False)[:500])
            raise RuntimeError("ASR 任务成功，但未返回任何转写结果")
        logger.info("[ASR] 提取到 %d 条转写结果", len(transcripts))
        return self._format_transcripts(transcripts, title)

    def _extract_transcripts(self, result: dict) -> list:
        def _coerce_transcript_item(item) -> list[dict]:
            if not isinstance(item, dict):
                return []
            if isinstance(item.get("transcripts"), list):
                output_items = []
                for sub in item.get("transcripts", []):
                    output_items.extend(_coerce_transcript_item(sub))
                return output_items
            if isinstance(item.get("sentences"), list):
                return [{
                    "sentences": item.get("sentences", []),
                    "text": item.get("text", ""),
                }]
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                transcript = {"text": text.strip(), "sentences": []}
                time_range = _extract_time_range_ms(item)
                if time_range is not None:
                    transcript["time_range_ms"] = time_range
                return [transcript]
            return []

        def _collect_transcripts(payload) -> list[dict]:
            collected: list[dict] = []
            if isinstance(payload, dict):
                if isinstance(payload.get("transcripts"), list):
                    for transcript in payload["transcripts"]:
                        collected.extend(_coerce_transcript_item(transcript))
                if isinstance(payload.get("sentences"), list):
                    collected.extend(_coerce_transcript_item(payload))

                for key in ("output", "result", "results", "data", "data_list"):
                    if key in payload:
                        collected.extend(_collect_transcripts(payload[key]))
            elif isinstance(payload, list):
                for item in payload:
                    collected.extend(_collect_transcripts(item))
            return collected

        output = result.get("output", {})
        transcripts = []

        results = ([output.get("result")] if isinstance(output.get("result"), dict) else []) + output.get("results", [])
        for item in results:
            if not isinstance(item, dict):
                continue
            transcript_urls = []
            for key in ("transcription_url", "result_url", "url"):
                value = item.get(key)
                if isinstance(value, str) and value:
                    transcript_urls.append(value)

            for transcription_url in transcript_urls:
                normalized_url = _normalize_trusted_url(transcription_url, self._trusted_hosts)
                if not normalized_url:
                    logger.warning("[ASR] 拒绝不受信任的 transcription_url: %s", transcription_url)
                    continue
                try:
                    response = _retry_on_ssl(
                        lambda u=normalized_url: self._get_http_session().get(u, timeout=30),
                        4,
                        sleep_fn=self._sleep,
                    )
                    if response.status_code == 200:
                        transcripts.extend(_collect_transcripts(response.json()))
                except Exception as e:
                    logger.warning("[ASR] 下载转写结果失败: %s", e)

            transcripts.extend(_collect_transcripts(item))

        if not transcripts:
            transcripts = _collect_transcripts(output)

        # 去重，避免从 result/results/url 同时提取导致重复片段
        deduped = []
        seen = set()
        for transcript in transcripts:
            key = json.dumps(transcript, ensure_ascii=False, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(transcript)
        transcripts = deduped

        return transcripts

    @staticmethod
    def _format_transcripts(transcripts: list, title: str) -> str:
        if not transcripts:
            raise RuntimeError(f"ASR 处理失败（无内容）: {title}")
        md = [f"<!-- meta:audio title={title} -->\n"]

        seg_idx = 0
        for transcript in transcripts:
            sentences = transcript.get("sentences", [])
            if not sentences:
                text = transcript.get("text", "")
                if text:
                    seg_idx += 1
                    time_range = transcript.get("time_range_ms")
                    if (
                        isinstance(time_range, (list, tuple))
                        and len(time_range) == 2
                        and time_range[0] is not None
                        and time_range[1] is not None
                        and time_range[1] >= time_range[0]
                    ):
                        md.extend([
                            f"<!-- meta:segment index={seg_idx} time={_ms_ts(time_range[0])}~{_ms_ts(time_range[1])} -->\n",
                            text,
                            "",
                        ])
                    else:
                        md.extend([f"<!-- meta:segment index={seg_idx} -->\n", text, ""])
                continue

            group = []
            group_start = None
            for idx, sentence in enumerate(sentences):
                begin = sentence.get("begin_time", 0)
                end = sentence.get("end_time", 0)
                if group_start is None:
                    group_start = begin
                group.append(sentence)

                gap = 0
                if idx + 1 < len(sentences):
                    gap = sentences[idx + 1].get("begin_time", 0) - end

                if end - group_start >= 60000 or gap > 3000:
                    seg_idx += 1
                    md.append(f"<!-- meta:segment index={seg_idx} time={_ms_ts(group_start)}~{_ms_ts(end)} -->\n")
                    md.append("".join(item.get("text", "") for item in group))
                    md.append("")
                    group = []
                    group_start = None

            if group:
                seg_idx += 1
                last_end = group[-1].get("end_time", 0)
                md.append(f"<!-- meta:segment index={seg_idx} time={_ms_ts(group_start)}~{_ms_ts(last_end)} -->\n")
                md.append("".join(item.get("text", "") for item in group))
                md.append("")

        return "\n".join(md)

    @staticmethod
    def _build_corpus(hotwords):
        if not hotwords:
            return ""
        deduped = list(dict.fromkeys(word.strip() for word in hotwords if word.strip()))
        return "、".join(deduped) if deduped else ""


def _is_remote(path: str) -> bool:
    return path.startswith(("http://", "https://", "oss://"))


def _uses_single_file_url(model_name: str) -> bool:
    """Qwen3-ASR-Flash-Filetrans uses input.file_url; classic ASR uses input.file_urls."""
    lowered = (model_name or "").lower()
    return "qwen" in lowered and "filetrans" in lowered


def _uses_dashscope_oss_upload(model_name: str) -> bool:
    """Local Qwen filetrans inputs must be uploaded as oss:// resources."""
    return _uses_single_file_url(model_name)


def _needs_dashscope_oss_resolver(file_url: str) -> bool:
    return (file_url or "").startswith("oss://")


def _coerce_ms_timestamp(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip()))
        except (TypeError, ValueError):
            return None
    return None


def _extract_time_range_ms(item: dict) -> tuple[int, int] | None:
    key_pairs = [
        ("begin_time", "end_time"),
        ("start_time", "end_time"),
        ("start_time", "stop_time"),
        ("begin", "end"),
    ]
    for start_key, end_key in key_pairs:
        start = _coerce_ms_timestamp(item.get(start_key))
        end = _coerce_ms_timestamp(item.get(end_key))
        if start is None or end is None:
            continue
        if end < start:
            continue
        return start, end
    return None


def _probe_duration(audio_path: str, ffprobe_path: str | None = None, cancel_event=None) -> float:
    if ffprobe_path:
        result = run_subprocess_cancellable(
            [
                ffprobe_path,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                audio_path,
            ],
            cancel_event=cancel_event,
            timeout=60,
            text=True,
            check=True,
        )
        output = (result.stdout or "").strip()
        if output:
            return float(output)

    ffmpeg_path = get_ffmpeg()
    result = run_subprocess_cancellable(
        [ffmpeg_path, "-i", audio_path],
        cancel_event=cancel_event,
        timeout=60,
        text=True,
        check=False,
    )
    stderr = result.stderr or ""
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr)
    if not match:
        raise RuntimeError(f"无法探测时长: {audio_path}")
    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = float(match.group(3))
    return hours * 3600 + minutes * 60 + seconds


def _ms_ts(ms: int) -> str:
    total = ms // 1000
    h, m, s = total // 3600, (total % 3600) // 60, total % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
