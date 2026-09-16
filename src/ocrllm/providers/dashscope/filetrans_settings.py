"""Secret-safe settings for the native DashScope FileTrans audio route."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
from urllib.parse import urlsplit

from ...errors import ConfigError


DEFAULT_DASHSCOPE_FILETRANS_BASE_URL = "https://dashscope.aliyuncs.com"
DEFAULT_DASHSCOPE_FILETRANS_MODEL = "qwen-audio-3.0-asr-flash-filetrans"


@dataclass(frozen=True, slots=True)
class DashScopeFileTransSettings:
    """Configure native async FileTrans without exposing credentials in repr."""

    api_key: str | None = field(default=None, repr=False)
    base_url: str = DEFAULT_DASHSCOPE_FILETRANS_BASE_URL
    task_state_dir: str | Path | None = None
    poll_interval_seconds: float = 3.0
    poll_timeout_seconds: float = 7200.0

    def __post_init__(self) -> None:
        _validate_base_url(self.base_url)
        if self.task_state_dir is None:
            raise ConfigError(
                "DashScope FileTrans requires a persistent task_state_dir outside temporary audio snapshots.",
                code="CONFIG_MISSING",
            ) from None
        if self.api_key is not None and not _is_clean_secret(self.api_key):
            raise ConfigError(
                "DashScopeFileTransSettings.api_key must be nonempty exact text.",
                code="CONFIG_INVALID",
            ) from None
        if self.task_state_dir is not None:
            if not isinstance(self.task_state_dir, (str, Path)) or not str(self.task_state_dir).strip():
                raise ConfigError(
                    "DashScopeFileTransSettings.task_state_dir must be a path when set.",
                    code="CONFIG_INVALID",
                ) from None
        for name in ("poll_interval_seconds", "poll_timeout_seconds"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or value <= 0
            ):
                raise ConfigError(
                    f"DashScopeFileTransSettings.{name} must be positive.",
                    code="CONFIG_INVALID",
                ) from None


def _is_clean_secret(value: object) -> bool:
    return (
        type(value) is str
        and bool(value)
        and value == value.strip()
        and not any(ord(char) < 32 or ord(char) == 127 for char in value)
    )


def _validate_base_url(value: object) -> None:
    if type(value) is not str or not value or value != value.strip():
        _raise_invalid_url()
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except (TypeError, ValueError):
        _raise_invalid_url()
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or (port is not None and not 1 <= port <= 65535)
        or parsed.path.rstrip("/")
    ):
        _raise_invalid_url()


def _raise_invalid_url() -> None:
    raise ConfigError(
        "DashScopeFileTransSettings.base_url must be an absolute HTTP(S) origin.",
        code="CONFIG_INVALID",
    ) from None
