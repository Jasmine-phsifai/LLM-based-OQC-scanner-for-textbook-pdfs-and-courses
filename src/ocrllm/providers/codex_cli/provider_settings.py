"""Immutable settings for the built-in Codex CLI vision provider."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from ...errors import ConfigError
from ...image_group_limits import MAX_IMAGE_GROUP_COUNT

DEFAULT_CODEX_CLI_MODEL = "gpt-5.6-luna"
DEFAULT_CODEX_CLI_REASONING_EFFORT = "low"
DEFAULT_CODEX_CLI_TIMEOUT_SECONDS = 1800.0
MAX_CODEX_CLI_TIMEOUT_SECONDS = 7200.0
DEFAULT_CODEX_CLI_MAX_IMAGES_PER_CALL = 8


@dataclass(frozen=True, slots=True)
class CodexCLISettings:
    """Select the local Codex CLI as the vision provider."""

    command: str = "codex"
    model: str = DEFAULT_CODEX_CLI_MODEL
    reasoning_effort: str = DEFAULT_CODEX_CLI_REASONING_EFFORT
    fast_mode: bool = False
    timeout_seconds: float = DEFAULT_CODEX_CLI_TIMEOUT_SECONDS
    max_images_per_call: int = DEFAULT_CODEX_CLI_MAX_IMAGES_PER_CALL
    service_tier: str | None = None
    usage_event_dir: str | Path | None = None
    course_validation: bool = False
    adjacent_repeat_limit: int | None = None

    def __post_init__(self) -> None:
        _require_clean_text(self.command, field_name="command", allow_inner_space=True)
        _require_clean_text(self.model, field_name="model", allow_inner_space=False)
        _require_clean_text(
            self.reasoning_effort,
            field_name="reasoning_effort",
            allow_inner_space=False,
        )
        if type(self.fast_mode) is not bool:
            raise ConfigError(
                "CodexCLISettings.fast_mode must be a boolean",
                code="CONFIG_INVALID",
            ) from None
        if self.service_tier is not None:
            _require_clean_text(self.service_tier, field_name="service_tier", allow_inner_space=False)
        if self.fast_mode and self.service_tier not in (None, "priority"):
            raise ConfigError("CodexCLISettings.service_tier conflicts with fast_mode.", code="CONFIG_INVALID")
        if type(self.course_validation) is not bool:
            raise ConfigError("CodexCLISettings.course_validation must be a boolean.", code="CONFIG_INVALID")
        if self.adjacent_repeat_limit is not None and (
            type(self.adjacent_repeat_limit) is not int or self.adjacent_repeat_limit < 3
        ):
            raise ConfigError("CodexCLISettings.adjacent_repeat_limit must be an integer >= 3 or None.", code="CONFIG_INVALID")
        if self.usage_event_dir is not None:
            if not isinstance(self.usage_event_dir, Path) and (
                type(self.usage_event_dir) is not str or not self.usage_event_dir.strip()
            ):
                raise ConfigError("CodexCLISettings.usage_event_dir must be a path.", code="CONFIG_INVALID")
            destination = Path(self.usage_event_dir)
            if not destination.is_absolute():
                raise ConfigError("CodexCLISettings.usage_event_dir must be absolute.", code="CONFIG_INVALID")
            object.__setattr__(self, "usage_event_dir", destination)
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(float(self.timeout_seconds))
            or not 0.0 < float(self.timeout_seconds) <= MAX_CODEX_CLI_TIMEOUT_SECONDS
        ):
            raise ConfigError(
                "CodexCLISettings.timeout_seconds must be a finite number in "
                f"(0, {MAX_CODEX_CLI_TIMEOUT_SECONDS:g}].",
                code="CONFIG_INVALID",
            ) from None
        object.__setattr__(self, "timeout_seconds", float(self.timeout_seconds))
        if (
            type(self.max_images_per_call) is not int
            or not 1 <= self.max_images_per_call <= MAX_IMAGE_GROUP_COUNT
        ):
            raise ConfigError(
                "CodexCLISettings.max_images_per_call must be an integer in "
                f"[1, {MAX_IMAGE_GROUP_COUNT}].",
                code="CONFIG_INVALID",
            ) from None


def resolve_codex_cli_model(name: str | None, settings: CodexCLISettings) -> str:
    """Let a caller-pinned vision model override the settings default."""
    return name if name is not None else settings.model


def _require_clean_text(
    value: object,
    *,
    field_name: str,
    allow_inner_space: bool,
) -> None:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or (not allow_inner_space and any(character.isspace() for character in value))
    ):
        raise ConfigError(
            f"CodexCLISettings.{field_name} must be nonempty exact text.",
            code="CONFIG_INVALID",
        ) from None
