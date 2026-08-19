"""Google Gemini SDK provider for OCRLLM.

This provider intentionally does not use the OpenAI-compatible Google endpoint.
Google mode is an independent backend that uses the official ``google-genai``
SDK so model listing, file uploads, and multimodal calls match AI Studio.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import os
import re
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import Event
from typing import Callable, Optional

import httpx

from OCRLLM.config import AppConfig
from OCRLLM.core import model_catalog
from OCRLLM.core.provider_errors import ProviderSetupError
from OCRLLM.core.task_runner import CancelledError

logger = logging.getLogger(__name__)


class GoogleErrorKind(str, Enum):
    QUOTA_EXHAUSTED = "quota_exhausted"
    RATE_LIMIT = "rate_limit"
    INVALID_MODEL = "invalid_model"
    NETWORK = "network"
    AUTH = "auth"
    BILLING = "billing"
    CONCURRENCY = "concurrency"
    EMPTY_RESPONSE = "empty_response"
    BAD_RESPONSE = "bad_response"
    SAFETY = "safety"
    UNKNOWN = "unknown"


TextValidator = Callable[[str], str | None]


@dataclass(frozen=True)
class ClassifiedGoogleError:
    kind: GoogleErrorKind
    should_switch_model: bool
    should_retry_same_model: bool
    message: str


class GoogleProviderFailure(RuntimeError):
    """Google provider error with a routing decision attached."""

    def __init__(self, classified: ClassifiedGoogleError):
        super().__init__(classified.message)
        self.classified = classified


class GoogleSDKDependencyError(ProviderSetupError):
    """Google SDK is missing or too old in the active Python environment."""


_NETWORK_ERRORS = (
    httpx.ConnectError,
    httpx.ReadError,
    httpx.WriteError,
    httpx.RemoteProtocolError,
    httpx.LocalProtocolError,
    httpx.ProtocolError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.PoolTimeout,
    ConnectionError,
    ConnectionResetError,
    OSError,
    TimeoutError,
)

_NETWORK_ERROR_TEXT_MARKERS = (
    "unexpected_eof_while_reading",
    "eof occurred in violation of protocol",
    "ssleoferror",
    "server disconnected without sending a response",
    "remote end closed connection",
    "connection reset",
    "connection aborted",
)

_AUDIO_RETRY_EXHAUSTED_SWITCH_KINDS = {
    GoogleErrorKind.RATE_LIMIT,
    GoogleErrorKind.CONCURRENCY,
    GoogleErrorKind.EMPTY_RESPONSE,
    GoogleErrorKind.BAD_RESPONSE,
}


def _google_audio_model_class(model: str) -> int:
    lowered = (model or "").lower()
    if "lite" in lowered:
        return 2
    elif "pro" in lowered:
        return 0
    elif "flash" in lowered:
        return 1
    return 3


def _google_sdk_dependency_error(feature: str, exc: Exception | None = None) -> GoogleSDKDependencyError:
    detail = f" ({type(exc).__name__}: {exc})" if exc else ""
    return GoogleSDKDependencyError(
        "当前 Python 环境缺少可用 google-genai SDK，无法使用 Google 模式"
        f"（{feature}）。\n"
        f"Python: {sys.executable}\n"
        "请在 OCRLLM 启动使用的同一环境执行:\n"
        "python -m pip install -r requirements.txt\n"
        '或: python -m pip install "google-genai>=1.53.0"'
        f"{detail}"
    )


def _load_google_genai():
    try:
        from google import genai
    except Exception as exc:
        raise _google_sdk_dependency_error("Client", exc) from exc
    if not hasattr(genai, "Client"):
        raise _google_sdk_dependency_error("Client")
    return genai


def _load_google_types():
    try:
        from google.genai import types
    except Exception as exc:
        raise _google_sdk_dependency_error("types.Part", exc) from exc
    part = getattr(types, "Part", None)
    if part is None or not hasattr(part, "from_bytes"):
        raise _google_sdk_dependency_error("types.Part")
    return types


def prioritize_google_audio_models(models: list[str]) -> list[str]:
    """Keep unique audio candidates, always trying Pro models before Flash/Lite."""
    deduped: list[str] = []
    seen = set()
    for model in models:
        if model and model not in seen:
            deduped.append(model)
            seen.add(model)
    ordered: list[str] = []
    for model_class in (0, 1, 2, 3):
        ordered.extend(model for model in deduped if _google_audio_model_class(model) == model_class)
    return ordered


def classify_google_error(exc: Exception) -> ClassifiedGoogleError:
    """Classify Google SDK/REST failures into retry or model-switch decisions."""
    message = str(exc)
    lowered = message.lower()

    if isinstance(exc, _NETWORK_ERRORS):
        return ClassifiedGoogleError(GoogleErrorKind.NETWORK, False, True, message)

    if any(marker in lowered for marker in _NETWORK_ERROR_TEXT_MARKERS):
        return ClassifiedGoogleError(GoogleErrorKind.NETWORK, False, True, message)

    json_error = _google_json_error_payload(message)
    if json_error is not None:
        return _classify_google_json_error(json_error, message)

    if "not_found" in lowered or '"code":404' in lowered or "code 404" in lowered or "404" in lowered and "model" in lowered:
        return ClassifiedGoogleError(GoogleErrorKind.INVALID_MODEL, True, False, message)
    if "quota" in lowered or "free tier" in lowered or "resource_exhausted" in lowered:
        if "rate limit" in lowered or "too many requests" in lowered or "rpm" in lowered or "tpm" in lowered or "rpd" in lowered:
            return ClassifiedGoogleError(GoogleErrorKind.RATE_LIMIT, False, True, message)
        return ClassifiedGoogleError(GoogleErrorKind.QUOTA_EXHAUSTED, True, False, message)
    if "permission_denied" in lowered or "unauthenticated" in lowered or "api key not valid" in lowered or "401" in lowered or "403" in lowered:
        return ClassifiedGoogleError(GoogleErrorKind.AUTH, False, False, message)
    if "billing" in lowered or "payment" in lowered or "insufficient" in lowered and "fund" in lowered:
        return ClassifiedGoogleError(GoogleErrorKind.BILLING, True, False, message)
    if (
        "500" in lowered
        or "internal" in lowered
        or "503" in lowered
        or "unavailable" in lowered
        or "high demand" in lowered
        or "try again later" in lowered
    ):
        if "internal" in lowered or "500" in lowered:
            return ClassifiedGoogleError(GoogleErrorKind.BAD_RESPONSE, False, True, message)
        return ClassifiedGoogleError(GoogleErrorKind.RATE_LIMIT, False, True, message)
    if "rate limit" in lowered or "too many requests" in lowered or "429" in lowered:
        return ClassifiedGoogleError(GoogleErrorKind.RATE_LIMIT, False, True, message)
    if "concurrent" in lowered or "concurrency" in lowered:
        return ClassifiedGoogleError(GoogleErrorKind.CONCURRENCY, False, True, message)
    if "safety" in lowered or "blocked" in lowered:
        return ClassifiedGoogleError(GoogleErrorKind.SAFETY, False, False, message)
    if "empty response" in lowered or "响应为空" in lowered:
        return ClassifiedGoogleError(GoogleErrorKind.EMPTY_RESPONSE, False, True, message)
    if "invalid_argument" in lowered or "400" in lowered:
        capability_markers = (
            "modality is not enabled",
            "input modality",
            "only supports",
            "is not supported",
            "does not support",
            "interactions api",
        )
        if any(marker in lowered for marker in capability_markers):
            return ClassifiedGoogleError(GoogleErrorKind.INVALID_MODEL, True, False, message)
        return ClassifiedGoogleError(GoogleErrorKind.BAD_RESPONSE, True, False, message)
    return ClassifiedGoogleError(GoogleErrorKind.UNKNOWN, False, False, message)


def _retry_delay_from_message(message: str) -> float | None:
    """Extract Google RetryInfo-style delays from SDK/REST error text."""
    patterns = (
        r'"retryDelay"\s*:\s*"(?P<value>\d+(?:\.\d+)?)s"',
        r"retry[_ ]?delay['\"]?\s*[:=]\s*['\"]?(?P<value>\d+(?:\.\d+)?)s",
        r"retry in (?P<value>\d+(?:\.\d+)?)\s*s",
    )
    lowered = message.lower()
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            return max(1.0, float(match.group("value")))
    seconds_match = re.search(r"seconds['\"]?\s*[:=]\s*(?P<value>\d+(?:\.\d+)?)", lowered)
    if "retry" in lowered and seconds_match:
        return max(1.0, float(seconds_match.group("value")))
    return None


def google_retry_delay_seconds(classified: ClassifiedGoogleError, attempt: int) -> float:
    """Choose retry delay without mistaking per-minute rate limits for transient errors."""
    hinted = _retry_delay_from_message(classified.message)
    if hinted is not None:
        return hinted
    exponential = min(2 ** max(0, attempt - 1), 60)
    if classified.kind == GoogleErrorKind.RATE_LIMIT:
        return max(65.0, float(exponential))
    return float(exponential)


def _field(value, name: str, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _response_text(response) -> str:
    text = _field(response, "text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    parts: list[str] = []
    for candidate in _field(response, "candidates", []) or []:
        content = _field(candidate, "content")
        for part in _field(content, "parts", []) or []:
            part_text = _field(part, "text")
            if isinstance(part_text, str) and part_text:
                parts.append(part_text)
    return "".join(parts).strip()


_GOOGLE_JSON_ERROR_STATUSES = {
    "aborted",
    "bad_request",
    "cancelled",
    "data_loss",
    "deadline_exceeded",
    "failed_precondition",
    "internal",
    "invalid_argument",
    "not_found",
    "out_of_range",
    "permission_denied",
    "resource_exhausted",
    "unauthenticated",
    "unavailable",
    "unknown",
}


def _coerce_error_code(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _google_json_error_payload(text: str) -> dict | None:
    stripped = text.strip()
    if not stripped.startswith("{"):
        # SDK 异常常形如 "400 INVALID_ARGUMENT. {'error': {...}}"：截取首个大括号后的部分。
        # 仅当前缀很短时才尝试，避免把含 JSON 片段的正常长响应误判为错误。
        brace = stripped.find("{")
        if brace == -1 or brace > 80:
            return None
        stripped = stripped[brace:]
    payload = None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        try:
            import ast

            payload = ast.literal_eval(stripped)
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            return None
    if not isinstance(payload, dict):
        return None

    raw_error = payload.get("error")
    if isinstance(raw_error, dict):
        payload = raw_error
    elif raw_error is not None:
        return payload

    code = _coerce_error_code(payload.get("code"))
    status = str(payload.get("status") or "").strip().lower()
    if code is not None and code >= 400:
        return payload
    if status in _GOOGLE_JSON_ERROR_STATUSES:
        return payload
    if "message" in payload and (code is not None or status):
        return payload
    return None


def _looks_like_json_error(text: str) -> bool:
    return _google_json_error_payload(text) is not None


def _classify_google_json_error(payload: dict, original_message: str) -> ClassifiedGoogleError:
    code = _coerce_error_code(payload.get("code"))
    status = str(payload.get("status") or "").strip().lower()
    message = str(payload.get("message") or original_message)
    lowered = " ".join([status, str(code or ""), message, original_message]).lower()

    if code == 404 or status == "not_found" or ("not found" in lowered and "model" in lowered):
        return ClassifiedGoogleError(GoogleErrorKind.INVALID_MODEL, True, False, original_message)
    if (
        code in {401, 403}
        or status in {"permission_denied", "unauthenticated"}
        or "api key not valid" in lowered
    ):
        return ClassifiedGoogleError(GoogleErrorKind.AUTH, False, False, original_message)
    if "billing" in lowered or "payment" in lowered or ("insufficient" in lowered and "fund" in lowered):
        return ClassifiedGoogleError(GoogleErrorKind.BILLING, True, False, original_message)
    if code == 429 or status == "resource_exhausted" or "quota" in lowered:
        if (
            code == 429
            or "rate limit" in lowered
            or "too many requests" in lowered
            or "rpm" in lowered
            or "tpm" in lowered
            or "rpd" in lowered
        ):
            return ClassifiedGoogleError(GoogleErrorKind.RATE_LIMIT, False, True, original_message)
        return ClassifiedGoogleError(GoogleErrorKind.QUOTA_EXHAUSTED, True, False, original_message)
    if "safety" in lowered or "blocked" in lowered:
        return ClassifiedGoogleError(GoogleErrorKind.SAFETY, False, False, original_message)
    if code and code >= 500:
        if "high demand" in lowered or "try again later" in lowered:
            return ClassifiedGoogleError(GoogleErrorKind.RATE_LIMIT, False, True, original_message)
        return ClassifiedGoogleError(GoogleErrorKind.BAD_RESPONSE, False, True, original_message)
    if status in {"internal", "unavailable", "deadline_exceeded"}:
        if "high demand" in lowered or "try again later" in lowered:
            return ClassifiedGoogleError(GoogleErrorKind.RATE_LIMIT, False, True, original_message)
        return ClassifiedGoogleError(GoogleErrorKind.BAD_RESPONSE, False, True, original_message)
    if code == 400 or status in {"invalid_argument", "bad_request", "failed_precondition", "aborted"}:
        # 模型能力不匹配（不支持图片输入 / 仅支持其他 API）：该模型永远失败，必须换模型
        capability_markers = (
            "modality is not enabled",
            "input modality",
            "only supports",
            "is not supported",
            "does not support",
            "interactions api",
        )
        if any(marker in lowered for marker in capability_markers):
            return ClassifiedGoogleError(GoogleErrorKind.INVALID_MODEL, True, False, original_message)
        # 其余 400 属于对该模型的永久性请求错误：先重试同模型（可能是瞬时），失败后换模型
        return ClassifiedGoogleError(GoogleErrorKind.BAD_RESPONSE, True, True, original_message)
    return ClassifiedGoogleError(GoogleErrorKind.BAD_RESPONSE, False, True, original_message)


class GoogleProviderClient:
    """Official Google Gemini SDK client with OCRLLM-compatible methods."""

    def __init__(self, cfg: Optional[AppConfig] = None, cancel_event: Optional[Event] = None):
        self.cfg = cfg or AppConfig()
        self._cancel_event = cancel_event
        if not self.cfg.google_api.api_key:
            raise ValueError("未配置 Google API Key。请填入 Google AI Studio / Gemini API Key")
        self._client = None
        self._unavailable_models_by_kind: dict[str, set[str]] = {}
        self._last_successful_model_by_kind: dict[str, str] = {}

    def set_cancel_event(self, cancel_event: Optional[Event]):
        self._cancel_event = cancel_event

    def last_successful_model(self, kind: str) -> str | None:
        return self._last_successful_model_by_kind.get(kind)

    def _check_cancelled(self):
        if self._cancel_event and self._cancel_event.is_set():
            raise CancelledError("任务已取消")

    def _sleep_with_cancel(self, seconds: float):
        if seconds <= 0:
            return
        deadline = time.monotonic() + seconds
        while True:
            self._check_cancelled()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            if self._cancel_event:
                self._cancel_event.wait(min(0.2, remaining))
            else:
                time.sleep(min(0.2, remaining))

    def _get_client(self):
        if self._client is not None:
            return self._client
        genai = _load_google_genai()
        self._client = genai.Client(api_key=self.cfg.google_api.api_key)
        return self._client

    def _validate_text(self, text: str, text_validator: TextValidator | None = None) -> str:
        if not text.strip():
            raise GoogleProviderFailure(ClassifiedGoogleError(
                GoogleErrorKind.EMPTY_RESPONSE,
                should_switch_model=False,
                should_retry_same_model=True,
                message="Google SDK 响应为空",
            ))
        if _looks_like_json_error(text):
            classified = classify_google_error(RuntimeError(text))
            raise GoogleProviderFailure(classified)
        cleaned = text.strip()
        if text_validator:
            invalid_reason = text_validator(cleaned)
            if invalid_reason:
                raise GoogleProviderFailure(ClassifiedGoogleError(
                    GoogleErrorKind.BAD_RESPONSE,
                    should_switch_model=True,
                    should_retry_same_model=False,
                    message=f"Google 响应未通过内容校验: {invalid_reason}",
                ))
        return cleaned

    def _retry_same_model(
        self,
        model: str,
        invoke,
        max_retries: int,
        text_validator: TextValidator | None = None,
    ) -> str:
        for attempt in range(1, max_retries + 1):
            self._check_cancelled()
            try:
                return self._validate_text(invoke(model), text_validator=text_validator)
            except GoogleProviderFailure as exc:
                classified = exc.classified
            except Exception as exc:
                classified = classify_google_error(exc)

            if not classified.should_retry_same_model or attempt >= max_retries:
                raise GoogleProviderFailure(classified)
            delay = google_retry_delay_seconds(classified, attempt)
            logger.warning(
                "[GOOGLE] %s 可重试错误 (model=%s, 尝试 %d/%d, %.0fs 后重试): %s",
                classified.kind.value,
                model,
                attempt,
                max_retries,
                delay,
                classified.message[:200],
            )
            self._sleep_with_cancel(delay)
        raise RuntimeError("Google 重试循环异常结束")

    def _call_with_model_switch(
        self,
        primary_model: str,
        chain: list[str],
        kind: str,
        invoke,
        max_retries: int,
        text_validator: TextValidator | None = None,
    ) -> str:
        unavailable = self._unavailable_models_by_kind.setdefault(kind, set())
        preferred = self._last_successful_model_by_kind.get(kind)
        raw_ordered = []
        if preferred:
            raw_ordered.append(preferred)
        raw_ordered.append(primary_model)
        raw_ordered.extend(model for model in chain if model)
        ordered = []
        seen = set()
        for model in raw_ordered:
            if not model or model in seen:
                continue
            seen.add(model)
            if model in unavailable and model != preferred:
                continue
            ordered.append(model)
        if not ordered and raw_ordered:
            ordered = [model for model in dict.fromkeys(raw_ordered) if model]
        last_error: GoogleProviderFailure | None = None
        previous = primary_model
        for idx, model in enumerate(ordered):
            if idx > 0:
                logger.warning("[GOOGLE] 切换 %s 模型: %s -> %s", kind, previous, model)
            try:
                text = self._retry_same_model(model, invoke, max_retries, text_validator=text_validator)
                self._last_successful_model_by_kind[kind] = model
                return text
            except GoogleProviderFailure as exc:
                last_error = exc
                if exc.classified.should_switch_model:
                    unavailable.add(model)
                    previous = model
                    continue
                if (
                    kind == "audio"
                    and exc.classified.should_retry_same_model
                    and exc.classified.kind in _AUDIO_RETRY_EXHAUSTED_SWITCH_KINDS
                    and idx + 1 < len(ordered)
                ):
                    logger.warning(
                        "[GOOGLE] %s 模型重试耗尽，进入下一个音频候选: model=%s, error=%s",
                        kind,
                        model,
                        exc.classified.message[:200],
                    )
                    unavailable.add(model)
                    previous = model
                    continue
                raise
        if last_error is not None:
            if last_error.classified.kind in {GoogleErrorKind.RATE_LIMIT, GoogleErrorKind.QUOTA_EXHAUSTED}:
                raise RuntimeError(f"Google {kind} 额度或限速耗尽: {last_error}") from last_error
            raise RuntimeError(f"Google {kind} 候选模型均不可用: {last_error}") from last_error
        raise RuntimeError(f"Google {kind} 没有可用模型")

    def _make_image_part(self, image_path: str):
        types = _load_google_types()
        mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        with open(image_path, "rb") as f:
            data = f.read()
        return types.Part.from_bytes(data=data, mime_type=mime_type)

    @staticmethod
    def _history_to_text(history: Optional[list[dict]]) -> str:
        if not history:
            return ""
        lines = []
        for item in history:
            role = _field(item, "role", "")
            content = _field(item, "content", "")
            if isinstance(content, list):
                text = " ".join(str(_field(part, "text", "")) for part in content if _field(part, "text", ""))
            else:
                text = str(content)
            if text.strip():
                lines.append(f"{role}: {text.strip()}")
        return "\n".join(lines)

    def _vision_chain(self) -> list[str]:
        return self.cfg.google_api.vision_model_queue or model_catalog.google_free_vision_chain()

    def _audio_chain(self) -> list[str]:
        return prioritize_google_audio_models(
            self.cfg.google_api.audio_model_queue or model_catalog.google_free_audio_chain()
        )

    def _text_chain(self) -> list[str]:
        """Prefer general/audio-capable Gemini models for pure text, not image generators."""
        ordered: list[str] = []
        ordered.extend(self.cfg.google_api.audio_model_queue or model_catalog.google_free_audio_chain())
        ordered.extend(
            model.name
            for model in model_catalog.load_google_vision_models()
            if model.kind != "image_preview"
        )
        deduped: list[str] = []
        seen = set()
        for model in ordered:
            if model and model not in seen:
                deduped.append(model)
                seen.add(model)
        return deduped

    def chat_with_images(
        self,
        prompt: str,
        image_paths: list[str],
        model: Optional[str] = None,
        max_retries: int = 6,
    ) -> str:
        primary = model or self.cfg.google_api.vision_model
        parts = [self._make_image_part(path) for path in image_paths]
        parts.append(prompt)

        def _invoke(model_name: str) -> str:
            logger.info("[GOOGLE] 视觉请求: model=%s, 图片=%d", model_name, len(image_paths))
            response = self._get_client().models.generate_content(model=model_name, contents=parts)
            return _response_text(response)

        return self._call_with_model_switch(primary, self._vision_chain(), "vision", _invoke, max_retries)

    def chat_with_images_contextual(
        self,
        prompt: str,
        image_paths: list[str],
        history: Optional[list[dict]] = None,
        model: Optional[str] = None,
        max_retries: int = 6,
    ) -> str:
        history_text = self._history_to_text(history)
        contextual_prompt = prompt
        if history_text:
            contextual_prompt = (
                "以下历史上下文仅用于保持术语和编号一致，不要补充图片外内容。\n"
                f"{history_text}\n\n当前识别提示:\n{prompt}"
            )
        return self.chat_with_images(contextual_prompt, image_paths, model=model, max_retries=max_retries)

    def chat_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        history: Optional[list[dict]] = None,
        max_retries: int = 6,
    ) -> str:
        primary = model or self.cfg.google_api.text_model
        text_parts = []
        if system_prompt:
            text_parts.append(system_prompt)
        history_text = self._history_to_text(history)
        if history_text:
            text_parts.append(history_text)
        text_parts.append(prompt)
        contents = "\n\n".join(text_parts)

        def _invoke(model_name: str) -> str:
            logger.info("[GOOGLE] 文本请求: model=%s", model_name)
            response = self._get_client().models.generate_content(model=model_name, contents=contents)
            return _response_text(response)

        return self._call_with_model_switch(primary, self._text_chain(), "text", _invoke, max_retries)

    def _wait_file_ready(self, file_obj, timeout_seconds: float = 600.0):
        name = _field(file_obj, "name")
        deadline = time.monotonic() + timeout_seconds
        current = file_obj
        while True:
            state = _field(current, "state")
            state_name = str(_field(state, "name", state) or "").upper()
            if not state_name or state_name in {"ACTIVE", "SUCCEEDED", "READY"}:
                return current
            if state_name in {"FAILED", "ERROR"}:
                raise RuntimeError(f"Google Files API 文件处理失败: {state_name}")
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Google Files API 文件处理超时: {name or '<unknown>'}")
            self._sleep_with_cancel(2.0)
            if not name:
                return current
            current = self._get_client().files.get(name=name)

    @staticmethod
    def _ascii_safe_upload_copy(path: str) -> tuple[str, str | None]:
        try:
            path.encode("ascii")
            return path, None
        except UnicodeEncodeError:
            suffix = Path(path).suffix or ".audio"
            fd, tmp_path = tempfile.mkstemp(prefix="ocrllm-google-upload-", suffix=suffix)
            os.close(fd)
            shutil.copyfile(path, tmp_path)
            return tmp_path, tmp_path

    def transcribe_long_audio(
        self,
        audio_path: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        language: Optional[str] = None,
        max_retries: int = 4,
        text_validator: TextValidator | None = None,
    ) -> str:
        primary = model or self.cfg.google_api.audio_model
        prompt = system_prompt or "Generate a detailed transcript of the speech with timestamps when possible."
        if language:
            prompt += f"\nPreferred language code: {language}"
        display_name = os.path.basename(audio_path)

        uploaded = None

        def _invoke(model_name: str) -> str:
            nonlocal uploaded
            self._check_cancelled()
            if uploaded is None:
                logger.info("[GOOGLE] 上传音频到 Files API: %s", display_name)
                upload_path, cleanup_path = self._ascii_safe_upload_copy(audio_path)
                try:
                    uploaded = self._get_client().files.upload(file=upload_path)
                    uploaded = self._wait_file_ready(uploaded)
                finally:
                    if cleanup_path:
                        try:
                            os.unlink(cleanup_path)
                        except OSError:
                            logger.debug("[GOOGLE] 临时上传文件清理失败: %s", cleanup_path)
            logger.info("[GOOGLE] 长音频识别: model=%s, audio=%s", model_name, display_name)
            response = self._get_client().models.generate_content(model=model_name, contents=[prompt, uploaded])
            return _response_text(response)

        return self._call_with_model_switch(
            primary,
            self._audio_chain(),
            "audio",
            _invoke,
            max_retries,
            text_validator=text_validator,
        )

    def probe_vision_model(self, model: str, image_path: str, timeout: float = 60.0) -> tuple[bool, str]:
        try:
            text = self.chat_with_images("Read the visible text in this image.", [image_path], model=model, max_retries=1)
            return bool(text), text[:200]
        except Exception as exc:
            return False, str(exc)
