"""
LLM 客户端 — OpenAI 兼容接口封装，支持多模态和 ASR。

通过依赖注入 AppConfig 使用，不依赖全局状态。
"""

from __future__ import annotations

import base64
import logging
import os
import sys
import time
from pathlib import Path
from threading import Event
from typing import Optional
from urllib.parse import urlparse

import httpx
from openai import OpenAI, APIConnectionError, APITimeoutError, APIStatusError

from OCRLLM.config import AppConfig
from OCRLLM.core.codex_vision import CodexVisionRunner
from OCRLLM.core.task_runner import CancelledError

logger = logging.getLogger(__name__)

_NETWORK_ERRORS = (
    httpx.ConnectError, httpx.ReadError, httpx.WriteError,
    httpx.RemoteProtocolError, httpx.ConnectTimeout, httpx.ReadTimeout,
    httpx.PoolTimeout, httpx.HTTPStatusError,
    APIConnectionError, APITimeoutError,
    ConnectionError, ConnectionResetError, OSError, TimeoutError,
)
_RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def dashscope_local_file_uri(path: str) -> str:
    resolved = Path(path).resolve()
    if sys.platform == "win32":
        return "file://" + resolved.as_posix()
    return resolved.as_uri()


class EmptyResponseError(RuntimeError):
    """模型返回了空内容。"""


class FreeTierExhaustedError(RuntimeError):
    """该模型免费额度已用完 (DashScope 错误码 AllocationQuota.FreeTierOnly)。

    上层捕获到时应该尝试沿 free_*_chain() 切换下一个模型继续，
    所有候选都耗尽时再抛错给用户。
    """
    def __init__(self, model: str, original_message: str = ""):
        super().__init__(f"模型 {model} 免费额度耗尽: {original_message[:200]}")
        self.model = model
        self.original_message = original_message


class VisionQueueAdvanceError(RuntimeError):
    """An opted-in temporary provider failure that should try the next vision model."""

    def __init__(self, model: str, original_error: Exception):
        super().__init__(f"model {model} temporary provider failure: {original_error}")
        self.model = model
        self.original_error = original_error


def _looks_like_free_tier_exhausted(exc: Exception) -> bool:
    """检查异常是否对应 AllocationQuota.FreeTierOnly。"""
    msg = str(exc)
    if "AllocationQuota.FreeTierOnly" in msg or "FreeTierOnly" in msg:
        return True
    # 部分错误体形如：{"code":"FreeAllocationQuotaExceeded", ...}
    if "FreeAllocationQuota" in msg:
        return True
    return False


def _status_code(exc: Exception) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
    try:
        return int(status_code) if status_code is not None else None
    except (TypeError, ValueError):
        return None


def _should_advance_vision_queue(exc: Exception, vision_api, *, enabled: bool) -> bool:
    if _looks_like_free_tier_exhausted(exc):
        return True
    if not enabled or not vision_api.advance_queue_on_retriable_errors:
        return False
    if not vision_api.vision_model_queue:
        return False
    return _status_code(exc) in _RETRIABLE_STATUS_CODES


def _vision_queue_advance_error(model: str, exc: Exception) -> RuntimeError:
    if _looks_like_free_tier_exhausted(exc):
        return FreeTierExhaustedError(model, str(exc))
    return VisionQueueAdvanceError(model, exc)


def _is_retriable(exc: Exception) -> bool:
    if isinstance(exc, FreeTierExhaustedError):
        return False  # 用模型切换处理，不要让 _retry_call 反复重试
    if isinstance(exc, _NETWORK_ERRORS):
        return True
    if isinstance(exc, EmptyResponseError):
        return True
    if isinstance(exc, APIStatusError) and exc.status_code in _RETRIABLE_STATUS_CODES:
        # 429 里也可能是 FreeTierOnly；先排除掉再说
        if _looks_like_free_tier_exhausted(exc):
            return False
        return True
    return False


def _field(value, name: str, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _content_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            text = _content_text(_field(item, "text"))
            if not text and isinstance(item, str):
                text = item
            if not text:
                text = _content_text(_field(item, "content"))
            if text:
                parts.append(text)
        return "".join(parts)
    text = _field(content, "text")
    if text:
        return str(text)
    nested = _field(content, "content")
    if nested is not None and nested is not content:
        return _content_text(nested)
    return ""


def _first_choice(response):
    choices = _field(response, "choices") or []
    if not choices:
        return None
    return choices[0]


# 进程级单例：免费模型切换通知回调（GUI 在启动时挂上去，弹一次警告）
_FREE_TIER_NOTIFIER = None


def set_free_tier_notifier(callback) -> None:
    """注册免费模型切换的回调。callback(old_model, new_model, kind) -> None。"""
    global _FREE_TIER_NOTIFIER
    _FREE_TIER_NOTIFIER = callback


def _notify_free_tier_switch(old_model: str, new_model: str, kind: str) -> None:
    if _FREE_TIER_NOTIFIER is None:
        return
    try:
        _FREE_TIER_NOTIFIER(old_model, new_model, kind)
    except Exception as exc:
        logger.warning("[FREE_TIER] 通知回调失败: %s", exc)


class LLMClient:
    """OpenAI 兼容多模态 LLM 客户端。线程安全（OpenAI SDK 内部使用 httpx 连接池）。"""

    def __init__(self, cfg: Optional[AppConfig] = None, cancel_event: Optional[Event] = None):
        self.cfg = cfg or AppConfig()
        self._cancel_event = cancel_event
        primary_key = self.cfg.api.api_key
        primary_base_url = self.cfg.api.base_url
        if not primary_key and self.cfg.vision_api.enabled:
            primary_key = self.cfg.vision_api.api_key
            primary_base_url = self._normalize_openai_base_url(self.cfg.vision_api.base_url)
        self.codex_vision = CodexVisionRunner(self.cfg.codex_vision) if self.cfg.codex_vision.enabled else None
        if not primary_key and not self.cfg.codex_vision.enabled:
            raise ValueError(
                "未配置 API Key。请设置 DASHSCOPE_API_KEY 或视觉 Provider API Key"
            )
        self.client = None
        self.vision_client = None
        if primary_key:
            self.client = OpenAI(
                api_key=primary_key,
                base_url=primary_base_url,
                timeout=httpx.Timeout(300, connect=60),
                max_retries=0,
            )
            self.vision_client = self._build_vision_client()

    @staticmethod
    def _normalize_openai_base_url(base_url: str) -> str:
        normalized = (base_url or "").strip().rstrip("/")
        if not normalized:
            return normalized
        parsed = urlparse(normalized)
        if parsed.scheme and parsed.netloc and parsed.path in {"", "/"}:
            return f"{normalized}/v1"
        return normalized

    def _build_vision_client(self) -> OpenAI:
        vision_api = self.cfg.vision_api
        if not vision_api.enabled:
            return self.client
        if not vision_api.api_key:
            raise ValueError("视觉 Provider 已启用，但未配置视觉 API Key")
        if not vision_api.base_url:
            raise ValueError("视觉 Provider 已启用，但未配置视觉 Base URL")
        return OpenAI(
            api_key=vision_api.api_key,
            base_url=self._normalize_openai_base_url(vision_api.base_url),
            timeout=httpx.Timeout(300, connect=60),
            max_retries=0,
        )

    def _active_vision_client(self) -> OpenAI:
        client = self.vision_client if self.cfg.vision_api.enabled else self.client
        if client is None:
            raise ValueError("当前没有可用的 API 视觉客户端")
        return client

    def set_cancel_event(self, cancel_event: Optional[Event]):
        """设置取消事件，用于协作式中断正在进行的请求。

        Args:
            cancel_event: 线程取消事件，或 None 清除。
        """
        self._cancel_event = cancel_event

    @staticmethod
    def _collect_stream(stream) -> str:
        parts = []
        chunk_count = 0
        for chunk in stream:
            chunk_count += 1
            if isinstance(chunk, str):
                parts.append(chunk)
                continue
            choice = _first_choice(chunk)
            if choice is None:
                continue
            delta = _field(choice, "delta") or _field(choice, "message") or choice
            text = _content_text(_field(delta, "content") or _field(delta, "text"))
            if text:
                parts.append(text)
        result = "".join(parts)
        if not result and chunk_count > 0:
            logger.warning("[LLM] 流式响应为空 (收到 %d 个 chunk)", chunk_count)
        return result

    @staticmethod
    def _extract_message_text(completion) -> str:
        if isinstance(completion, str):
            return completion.strip()
        choice = _first_choice(completion)
        if choice is None:
            return _content_text(_field(completion, "output_text")).strip()
        message = _field(choice, "message") or _field(choice, "delta") or choice
        return _content_text(_field(message, "content") or _field(message, "text")).strip()

    @staticmethod
    def _encode_file(file_path: str, mime_map: dict[str, str], default_mime: str) -> str:
        ext = Path(file_path).suffix.lower()
        mime = mime_map.get(ext, default_mime)
        with open(file_path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime};base64,{data}"

    _IMAGE_MIME_MAP = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
        ".tif": "image/tiff", ".tiff": "image/tiff",
    }
    _AUDIO_MIME_MAP = {
        ".mp3": "audio/mpeg", ".wav": "audio/wav", ".aac": "audio/aac",
        ".m4a": "audio/mp4", ".amr": "audio/amr", ".ogg": "audio/ogg",
        ".flac": "audio/flac", ".3gp": "audio/3gpp",
    }

    @classmethod
    def _encode_image(cls, image_path: str) -> str:
        return cls._encode_file(image_path, cls._IMAGE_MIME_MAP, "image/jpeg")

    @classmethod
    def _encode_audio(cls, audio_path: str) -> str:
        return cls._encode_file(audio_path, cls._AUDIO_MIME_MAP, "audio/mpeg")

    def _check_cancelled(self):
        if self._cancel_event and self._cancel_event.is_set():
            raise CancelledError("任务已取消")

    def _sleep_with_cancel(self, seconds: float):
        if seconds <= 0:
            return
        if not self._cancel_event:
            time.sleep(seconds)
            return

        deadline = time.monotonic() + seconds
        while True:
            self._check_cancelled()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            self._cancel_event.wait(min(0.2, remaining))

    def _chat_with_stream_fallback(
        self,
        model: str,
        messages: list[dict],
        *,
        client: Optional[OpenAI] = None,
        extra_body: Optional[dict] = None,
        queue_on_retriable_errors: bool = False,
        retry_nonstream_on_stream_status_error: bool = False,
    ) -> str:
        api_client = client or self.client
        if api_client is None:
            raise ValueError("当前没有可用的 API 客户端")
        self._check_cancelled()
        request_kwargs = {
            "model": model,
            "messages": messages,
        }
        if extra_body:
            request_kwargs["extra_body"] = extra_body

        def _nonstream_result() -> str:
            completion = api_client.chat.completions.create(
                **request_kwargs,
                stream=False,
            )
            result = self._extract_message_text(completion)
            if result:
                return result
            raise EmptyResponseError("LLM 响应为空")

        try:
            stream = api_client.chat.completions.create(
                **request_kwargs,
                stream=True,
            )
            result = self._collect_stream(stream)
        except Exception as exc:
            if retry_nonstream_on_stream_status_error and _status_code(exc) in _RETRIABLE_STATUS_CODES:
                logger.warning("[LLM] 流式请求返回 %s，回退到非流式请求", _status_code(exc))
                try:
                    return _nonstream_result()
                except Exception as fallback_exc:
                    if _should_advance_vision_queue(
                        fallback_exc, self.cfg.vision_api, enabled=queue_on_retriable_errors
                    ):
                        raise _vision_queue_advance_error(model, fallback_exc) from fallback_exc
                    raise
            if _should_advance_vision_queue(
                exc, self.cfg.vision_api, enabled=queue_on_retriable_errors
            ):
                raise _vision_queue_advance_error(model, exc) from exc
            raise
        if result:
            return result

        logger.warning("[LLM] 流式响应为空，回退到非流式请求")
        try:
            return _nonstream_result()
        except Exception as exc:
            if _should_advance_vision_queue(
                exc, self.cfg.vision_api, enabled=queue_on_retriable_errors
            ):
                raise _vision_queue_advance_error(model, exc) from exc
            raise

    @staticmethod
    def _extract_responses_text(response) -> str:
        text = _field(response, "output_text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        parts: list[str] = []
        for item in _field(response, "output", []) or []:
            for content in _field(item, "content", []) or []:
                content_text = _content_text(_field(content, "text") or _field(content, "content"))
                if content_text:
                    parts.append(content_text)
        return "".join(parts).strip()

    def _responses_payload(self, model: str, prompt: str, image_paths: list[str]) -> dict:
        content = [{"type": "input_text", "text": prompt}]
        for img in image_paths:
            content.append({"type": "input_image", "image_url": self._encode_image(img)})
        payload = {
            "model": model,
            "input": [{"role": "user", "content": content}],
        }
        vision_api = self.cfg.vision_api
        if vision_api.model_reasoning_effort:
            payload["reasoning"] = {"effort": vision_api.model_reasoning_effort}
        if vision_api.network_access:
            payload["tools"] = [{"type": "web_search_preview"}]
        if vision_api.disable_response_storage:
            payload["store"] = False
        return payload

    def _responses_with_images(self, model: str, prompt: str, image_paths: list[str]) -> str:
        self._check_cancelled()
        try:
            response = self._active_vision_client().responses.create(**self._responses_payload(model, prompt, image_paths))
        except Exception as exc:
            if _should_advance_vision_queue(
                exc, self.cfg.vision_api, enabled=self.cfg.vision_api.enabled
            ):
                raise _vision_queue_advance_error(model, exc) from exc
            raise
        result = self._extract_responses_text(response)
        if result:
            return result
        raise EmptyResponseError("Responses API 响应为空")

    def _chat_messages_for_images(self, prompt: str, image_paths: list[str]) -> list[dict]:
        content = [{"type": "text", "text": prompt}]
        for img in image_paths:
            content.append({
                "type": "image_url",
                "image_url": {"url": self._encode_image(img)},
            })
        return [{"role": "user", "content": content}]

    def _vision_chat_extra_body(self) -> Optional[dict]:
        if not self.cfg.vision_api.enabled:
            return {"enable_thinking": False}
        base_url = (self.cfg.vision_api.base_url or "").lower()
        if "dashscope" in base_url or "aliyuncs" in base_url:
            return {"enable_thinking": False}
        return None

    def _vision_with_images(self, model: str, prompt: str, image_paths: list[str], messages: Optional[list[dict]] = None) -> str:
        if self.cfg.vision_api.enabled and self.cfg.vision_api.wire_api.lower() == "responses":
            return self._responses_with_images(model, prompt, image_paths)
        return self._chat_with_stream_fallback(
            model,
            messages or self._chat_messages_for_images(prompt, image_paths),
            client=self._active_vision_client(),
            extra_body=self._vision_chat_extra_body(),
            queue_on_retriable_errors=self.cfg.vision_api.enabled,
            retry_nonstream_on_stream_status_error=self.cfg.vision_api.enabled,
        )

    def _vision_fallback_chain(self) -> list[str]:
        if self.cfg.vision_api.enabled:
            # 视觉独立 Provider 的模型降级队列（用户配置的优先级顺序）
            q = self.cfg.vision_api.vision_model_queue
            if q:
                primary = self.cfg.models.vision_model
                return [m for m in q if m != primary]
            return []
        from OCRLLM.core import model_catalog
        return model_catalog.free_vision_chain()

    def _call_with_model_fallback(
        self,
        primary_model: str,
        chain: list[str],
        kind: str,
        invoke,
    ):
        """在明确免费额度耗尽或已启用的视觉临时故障策略下切换候选模型。

        Args:
            primary_model: 用户优先选用的模型。
            chain: 按顺序排列的候选模型。
            kind: 请求类型，仅用于日志和免费额度通知。
            invoke: callable(model_name) -> str。

        Returns:
            invoke 返回值。

        Raises:
            FreeTierExhaustedError: 所有候选都明确耗尽免费额度时抛出。
            Exception: 临时故障候选队列耗尽时重新抛出原始供应商异常。
        """
        # 把 primary_model 提到链头，避免重复
        ordered = [primary_model] + [m for m in chain if m != primary_model]
        last_exc: FreeTierExhaustedError | VisionQueueAdvanceError | None = None
        saw_temporary_failure = False
        previous_model = primary_model
        for idx, model_name in enumerate(ordered):
            try:
                if idx > 0:
                    if isinstance(last_exc, FreeTierExhaustedError):
                        logger.warning("[FREE_TIER] 切换到 %s 继续 (%s)", model_name, kind)
                        _notify_free_tier_switch(previous_model, model_name, kind)
                    else:
                        logger.warning(
                            "[VISION_FAILOVER] temporary provider failure; switching to %s (%s)",
                            model_name,
                            kind,
                        )
                return invoke(model_name)
            except FreeTierExhaustedError as exc:
                logger.warning("[FREE_TIER] %s 免费额度耗尽 (%s)", model_name, exc.original_message[:120])
                last_exc = exc
                previous_model = model_name
                continue
            except VisionQueueAdvanceError as exc:
                logger.warning(
                    "[VISION_FAILOVER] %s temporary provider failure (%s)",
                    model_name,
                    str(exc.original_error)[:120],
                )
                last_exc = exc
                saw_temporary_failure = True
                previous_model = model_name
                continue
        if isinstance(last_exc, VisionQueueAdvanceError):
            raise last_exc.original_error from last_exc
        if isinstance(last_exc, FreeTierExhaustedError):
            if saw_temporary_failure:
                raise last_exc
            raise FreeTierExhaustedError(
                f"all-{kind}",
                f"所有 {kind} 免费额度模型均已耗尽，最后尝试的是 {previous_model}",
            )

    def _retry_call(self, fn, max_retries: int = 6, retry_delay: float = 5.0):
        for attempt in range(1, max_retries + 1):
            try:
                self._check_cancelled()
                return fn()
            except Exception as e:
                if not _is_retriable(e):
                    logger.error("[LLM] 不可重试错误，立即抛出: %s", e)
                    raise
                delay = min(retry_delay * (2 ** (attempt - 1)), 120)
                logger.warning("[LLM] 网络错误 (尝试 %d/%d, %.0fs 后重试): %s",
                               attempt, max_retries, delay, e)
                if attempt < max_retries:
                    self._sleep_with_cancel(delay)
                    continue
                raise

    def chat_with_images(
        self,
        prompt: str,
        image_paths: list[str],
        model: Optional[str] = None,
        max_retries: int = 6,
    ) -> str:
        """发送图片+文本的多模态请求。

        Args:
            prompt: 文本提示词。
            image_paths: 图片文件路径列表。
            model: 模型名称，默认使用 vision_model。
            max_retries: 最大重试次数。

        Returns:
            LLM 响应文本。

        Raises:
            EmptyResponseError: LLM 返回空响应。
        """
        if self.codex_vision is not None:
            return self.codex_vision.recognize(prompt, image_paths)

        primary_model = model or self.cfg.models.vision_model
        messages = self._chat_messages_for_images(prompt, image_paths)

        def _call_one(model_name: str):
            def _call():
                logger.info("[LLM] 发送请求: model=%s, 图片=%d", model_name, len(image_paths))
                result = self._vision_with_images(model_name, prompt, image_paths, messages)
                logger.info("[LLM] 收到响应: %d 字符", len(result))
                return result
            return self._retry_call(_call, max_retries)

        chain = self._vision_fallback_chain()
        return self._call_with_model_fallback(primary_model, chain, "vision", _call_one)

    def chat_with_images_contextual(
        self,
        prompt: str,
        image_paths: list[str],
        history: Optional[list[dict]] = None,
        model: Optional[str] = None,
        max_retries: int = 6,
    ) -> str:
        """带历史上下文的图片+文本多模态请求。

        Args:
            prompt: 文本提示词。
            image_paths: 图片文件路径列表。
            history: 历史对话消息列表。
            model: 模型名称，默认使用 vision_model。
            max_retries: 最大重试次数。

        Returns:
            LLM 响应文本。
        """
        if self.codex_vision is not None:
            contextual_prompt = prompt
            if history:
                history_text = "\n".join(
                    _content_text(_field(item, "content"))
                    for item in history
                    if _content_text(_field(item, "content"))
                )
                if history_text:
                    contextual_prompt = (
                        "以下历史上下文仅用于保持术语和编号一致，不要补充图片外内容。\n"
                        f"{history_text}\n\n当前识别提示:\n{prompt}"
                    )
            return self.codex_vision.recognize(contextual_prompt, image_paths)

        primary_model = model or self.cfg.models.vision_model
        messages = list(history) if history else []
        content = [{"type": "text", "text": prompt}]
        for img in image_paths:
            content.append({
                "type": "image_url",
                "image_url": {"url": self._encode_image(img)},
            })
        messages.append({"role": "user", "content": content})

        def _call_one(model_name: str):
            def _call():
                logger.info("[LLM] 上下文请求: model=%s, 图片=%d, 历史=%d",
                            model_name, len(image_paths), len(history or []))
                result = self._vision_with_images(model_name, prompt, image_paths, messages)
                logger.info("[LLM] 收到响应: %d 字符", len(result))
                return result
            return self._retry_call(_call, max_retries)

        chain = self._vision_fallback_chain()
        return self._call_with_model_fallback(primary_model, chain, "vision", _call_one)

    def chat_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        history: Optional[list[dict]] = None,
        max_retries: int = 6,
    ) -> str:
        """发送纯文本请求。

        Args:
            prompt: 用户消息文本。
            system_prompt: 系统提示词。
            model: 模型名称，默认使用 text_model。
            history: 历史对话消息列表。
            max_retries: 最大重试次数。

        Returns:
            LLM 响应文本。
        """
        primary_model = model or self.cfg.models.text_model
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        def _call_one(model_name: str):
            def _call():
                return self._chat_with_stream_fallback(model_name, messages, extra_body={"enable_thinking": False})
            return self._retry_call(_call, max_retries)

        from OCRLLM.core import model_catalog
        chain = model_catalog.free_vision_chain()  # 文本任务沿用视觉链（含 general 类型）
        return self._call_with_model_fallback(primary_model, chain, "text", _call_one)

    def transcribe_short_audio(
        self,
        audio_path: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        language: Optional[str] = None,
        enable_itn: bool = False,
        max_retries: int = 6,
    ) -> str:
        """调用 ASR 模型识别短音频。

        Args:
            audio_path: 音频文件路径或 data URI。
            system_prompt: 系统提示词。
            model: ASR 模型名称。
            language: 语言代码。
            enable_itn: 是否启用逆文本正则化。
            max_retries: 最大重试次数。

        Returns:
            音频转写文本。
        """
        model = model or self.cfg.models.asr_short_model
        prefer_dashscope_sdk = self._is_dashscope_api()
        if prefer_dashscope_sdk:
            try:
                return self._transcribe_short_audio_dashscope_sdk(
                    audio_path=audio_path,
                    system_prompt=system_prompt,
                    model=model,
                    language=language,
                    enable_itn=enable_itn,
                    max_retries=max_retries,
                )
            except Exception as exc:
                logger.warning("[LLM] DashScope SDK 短音频识别失败，回退 OpenAI 兼容: %s", exc)
        return self._transcribe_short_audio_openai_compatible(
            audio_path=audio_path,
            system_prompt=system_prompt,
            model=model,
            language=language,
            enable_itn=enable_itn,
            max_retries=max_retries,
        )

    def _is_dashscope_api(self) -> bool:
        marker = (self.cfg.api.base_url or "").lower()
        return "dashscope" in marker or "aliyuncs.com" in marker or "maas.aliyuncs.com" in marker

    def _transcribe_short_audio_openai_compatible(
        self,
        audio_path: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        language: Optional[str] = None,
        enable_itn: bool = False,
        max_retries: int = 6,
    ) -> str:
        model = model or self.cfg.models.asr_short_model
        if audio_path.startswith(("http://", "https://", "data:")):
            audio_ref = audio_path
        else:
            audio_ref = self._encode_audio(audio_path)

        messages = [{
            "role": "user",
            "content": [{"type": "input_audio", "input_audio": {"data": audio_ref}}],
        }]
        asr_options = {"enable_itn": enable_itn}
        if language:
            asr_options["language"] = language

        def _call():
            logger.info("[LLM] 短音频识别: model=%s, audio=%s",
                        model, os.path.basename(audio_path))
            completion = self.client.chat.completions.create(
                model=model, messages=messages, stream=False,
                extra_body={"asr_options": asr_options},
            )
            result = self._extract_message_text(completion)
            if not result:
                raise EmptyResponseError("ASR 响应为空")
            logger.info("[LLM] 短音频识别完成: %d 字符", len(result))
            return result

        return self._retry_call(_call, max_retries)

    def _transcribe_short_audio_dashscope_sdk(
        self,
        audio_path: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        language: Optional[str] = None,
        enable_itn: bool = False,
        max_retries: int = 6,
    ) -> str:
        """Use DashScope SDK for short ASR, with OpenAI-compatible kept as fallback.

        两条短音频实现同时保留：后续接入其他音频识别模型时，OpenAI-compatible
        是通用路径；当 DashScope SDK 或原生路径临时不可用时，同一段音频还能用
        OpenAI 格式对 Qwen API 做兜底重试。
        """
        model = model or self.cfg.models.asr_short_model

        def _call():
            try:
                import dashscope
                from http import HTTPStatus
            except Exception as exc:
                raise RuntimeError(f"dashscope SDK 不可用: {exc}") from exc

            if audio_path.startswith(("http://", "https://", "data:")):
                audio_ref = audio_path
            else:
                audio_ref = dashscope_local_file_uri(audio_path)

            asr_options = {"enable_itn": enable_itn}
            if language:
                asr_options["language"] = language
            if system_prompt:
                asr_options["prompt"] = system_prompt

            logger.info("[LLM] DashScope SDK 短音频识别: model=%s, audio=%s", model, os.path.basename(audio_path))
            response = dashscope.MultiModalConversation.call(
                api_key=self.cfg.api.api_key,
                model=model,
                messages=[{"role": "user", "content": [{"audio": audio_ref}]}],
                asr_options=asr_options,
            )
            status_code = _field(response, "status_code")
            if status_code not in (None, HTTPStatus.OK, 200):
                code = _field(response, "code", "")
                message = _field(response, "message", "")
                raise RuntimeError(f"DashScope SDK ASR 失败: {status_code} {code} {message}")
            text = self._extract_dashscope_audio_text(response)
            if not text:
                raise EmptyResponseError("DashScope SDK ASR 响应为空")
            logger.info("[LLM] DashScope SDK 短音频识别完成: %d 字符", len(text))
            return text

        return self._retry_call(_call, max_retries)

    @staticmethod
    def _extract_dashscope_audio_text(response) -> str:
        output = _field(response, "output") or response
        choices = _field(output, "choices") or _field(response, "choices") or []
        parts: list[str] = []
        for choice in choices:
            message = _field(choice, "message") or choice
            text = _content_text(_field(message, "content") or _field(message, "text"))
            if text:
                parts.append(text)
        if parts:
            return "".join(parts).strip()
        return _content_text(_field(output, "text") or _field(response, "text")).strip()

    # ------------------------------------------------------------------
    # 模型可用性探测
    # ------------------------------------------------------------------

    def probe_vision_model(self, model: str, image_path: str, timeout: float = 60.0) -> tuple[bool, str]:
        """用一张真实图片探测视觉模型是否可用。

        Args:
            model: 待测试模型 ID。
            image_path: 真实图片路径（建议尺寸不大）。
            timeout: 单次请求超时（秒）。

        Returns:
            (ok, message)。message 在失败时携带后端错误片段。
        """
        try:
            text = self._vision_with_images(
                model,
                "请读取图片中的测试文字，并回复你读到的主要字符。",
                [image_path],
            )
            if not text:
                return False, "模型返回空响应"
            return True, text[:80]
        except APIStatusError as e:
            return False, f"HTTP {e.status_code}: {str(e)[:200]}"
        except Exception as e:
            return False, f"{type(e).__name__}: {str(e)[:200]}"

    def probe_audio_short_model(self, model: str, audio_path: str, timeout: float = 60.0) -> tuple[bool, str]:
        """用一段真实音频探测 OpenAI-兼容 ASR/Omni 模型是否可用。"""
        try:
            audio_ref = self._encode_audio(audio_path)
            messages = [{
                "role": "user",
                "content": [{"type": "input_audio", "input_audio": {"data": audio_ref}}],
            }]
            completion = self.client.chat.completions.create(
                model=model, messages=messages, stream=False,
                timeout=timeout,
                extra_body={"asr_options": {"enable_itn": False}},
            )
            text = self._extract_message_text(completion)
            if not text:
                return False, "模型返回空响应"
            return True, text[:80]
        except APIStatusError as e:
            return False, f"HTTP {e.status_code}: {str(e)[:200]}"
        except Exception as e:
            return False, f"{type(e).__name__}: {str(e)[:200]}"

    def probe_audio_filetrans_model(
        self,
        model: str,
        audio_url: str,
        poll_interval: float = 5.0,
        max_wait: float = 600.0,
    ) -> tuple[bool, str]:
        """通过 DashScope 原生异步 API 提交 filetrans 任务，验证模型可用。

        Args:
            model: 待测模型 ID。
            audio_url: 公网可访问的音频 URL（必须 >5min 才能验证长音频能力）。
            poll_interval: 轮询间隔（秒）。
            max_wait: 最大等待时长（秒）。

        Returns:
            (ok, message)。
        """
        import requests

        api_key = self.cfg.api.api_key
        if not api_key:
            return False, "未配置 API Key"
        from OCRLLM.processors.audio import _derive_asr_api_root
        api_root = _derive_asr_api_root(self.cfg.api.base_url)
        submit_url = f"{api_root}/api/v1/services/audio/asr/transcription"
        try:
            submit = requests.post(
                submit_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "enable",
                },
                json={
                    "model": model,
                    "input": {"file_urls": [audio_url]},
                    "parameters": {"channel_id": [0]},
                },
                timeout=30,
            )
            if submit.status_code != 200:
                return False, f"提交失败 HTTP {submit.status_code}: {submit.text[:200]}"
            task_id = submit.json().get("output", {}).get("task_id")
            if not task_id:
                return False, f"未返回 task_id: {submit.text[:200]}"
        except Exception as e:
            return False, f"提交异常 {type(e).__name__}: {str(e)[:200]}"

        deadline = time.monotonic() + max_wait
        url = f"{api_root}/api/v1/tasks/{task_id}"
        while time.monotonic() < deadline:
            try:
                resp = requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
                if resp.status_code != 200:
                    return False, f"轮询失败 HTTP {resp.status_code}: {resp.text[:200]}"
                output = resp.json().get("output", {})
                status = output.get("task_status")
                if status == "SUCCEEDED":
                    return True, "异步任务成功"
                if status == "FAILED":
                    return False, f"任务失败: {output.get('message', '')[:200]}"
            except Exception as e:
                return False, f"轮询异常 {type(e).__name__}: {str(e)[:200]}"
            time.sleep(poll_interval)
        return False, f"超时 ({max_wait:.0f}s) 仍未完成"
