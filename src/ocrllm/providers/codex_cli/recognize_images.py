"""Run one Codex CLI vision batch with transient-failure recovery."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path

from ...config import Config
from ...errors import (
    ConfigError,
    OCRLLMError,
    ProviderError,
    ProviderRequestInvalid,
    ProviderUnavailable,
)
from ...raise_if_cancelled import raise_if_cancelled
from .build_codex_exec_command import (
    build_codex_exec_command,
    build_codex_exec_prompt,
)
from .codex_exec_output import (
    is_image_access_refusal,
    parse_codex_refusal,
    summarize_codex_failure_output,
)
from .provider_settings import CodexCLISettings, resolve_codex_cli_model
from .stage_codex_images import stage_codex_images

_MAX_ATTEMPTS = 3
_RETRY_DELAY_SECONDS = 4.0
# Server-side attachment loss windows can last minutes; these long backoff
# delays retry outside the regular attempt budget.
_IMAGE_ACCESS_RETRY_DELAYS_SECONDS = (15.0, 45.0, 90.0, 180.0, 300.0)


def recognize_images(
    image_paths: Sequence[Path],
    *,
    prompt: str,
    config: Config,
) -> str:
    """Recognize one ordered image group through `codex exec`.

    The retry matrix lives here because only this adapter can tell Codex
    transport accidents (attachment loss, spawn resource pressure) apart from
    real refusals. Cancellation is honored between attempts; the spawned
    CLI call itself cannot be interrupted.
    """
    settings = config.provider
    if type(settings) is not CodexCLISettings:
        raise ConfigError(
            "The built-in Codex CLI provider requires exact CodexCLISettings.",
            code="CONFIG_INVALID",
            details={"provider_calls_attempted": 0},
        ) from None
    model = resolve_codex_cli_model(config.vision_model.name, settings)
    if shutil.which(settings.command) is None:
        raise ConfigError(
            "The Codex CLI command is not available on PATH; install Codex CLI "
            "or point CodexCLISettings.command at it.",
            code="CONFIG_MISSING",
            details={"provider": "codex_cli", "provider_calls_attempted": 0},
        ) from None
    if len(image_paths) > settings.max_images_per_call:
        raise ProviderRequestInvalid(
            "The Codex CLI provider accepts at most "
            f"{settings.max_images_per_call} images per call; "
            f"{len(image_paths)} were dispatched.",
            details={
                "provider": "codex_cli",
                "model": model,
                "provider_calls_attempted": 0,
            },
        ) from None

    with tempfile.TemporaryDirectory(prefix="ocrllm_codex_") as tmp:
        staging_dir = Path(tmp)
        try:
            staged_paths = stage_codex_images(image_paths, staging_dir)
        except OCRLLMError as error:
            error._add_safe_detail("provider_calls_attempted", 0)
            raise
        output_path = staging_dir / "last_message.txt"
        argv = build_codex_exec_command(
            command=settings.command,
            model=model,
            reasoning_effort=settings.reasoning_effort,
            fast_mode=settings.fast_mode,
            image_paths=staged_paths,
            cwd=staging_dir,
            output_path=output_path,
            prompt=build_codex_exec_prompt(prompt, len(staged_paths)),
        )

        attempt = 0
        image_access_retries = 0
        calls = 0
        while attempt < _MAX_ATTEMPTS:
            attempt += 1
            raise_if_cancelled(config.cancellation)
            if output_path.exists():
                output_path.unlink()
            calls += 1
            try:
                result = subprocess.run(
                    argv,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    stdin=subprocess.DEVNULL,
                    timeout=settings.timeout_seconds,
                    check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except subprocess.TimeoutExpired:
                raise ProviderError(
                    "The Codex CLI recognition exceeded its timeout.",
                    code="PROVIDER_TIMEOUT",
                    retryable=True,
                    details={
                        "provider": "codex_cli",
                        "model": model,
                        "timeout_seconds": settings.timeout_seconds,
                        "provider_calls_attempted": calls,
                    },
                ) from None
            except OSError as exc:
                # Spawn failures like WinError 1455 (paging file too small) are
                # transient resource pressure; wait and retry.
                if attempt < _MAX_ATTEMPTS:
                    _sleep_with_cancellation(
                        max(10.0, _RETRY_DELAY_SECONDS * attempt * 3),
                        config.cancellation,
                    )
                    continue
                raise ProviderUnavailable(
                    "The Codex CLI process could not be started.",
                    details={
                        "provider": "codex_cli",
                        "model": model,
                        "description": _single_line(str(exc)),
                        "provider_calls_attempted": calls,
                    },
                ) from None

            if result.returncode != 0:
                description = summarize_codex_failure_output(
                    result.stderr or result.stdout or "",
                    result.returncode,
                )
                if attempt < _MAX_ATTEMPTS:
                    _sleep_with_cancellation(
                        _RETRY_DELAY_SECONDS * attempt,
                        config.cancellation,
                    )
                    continue
                raise ProviderUnavailable(
                    "The Codex CLI recognition failed after repeated attempts.",
                    details={
                        "provider": "codex_cli",
                        "model": model,
                        "description": description,
                        "provider_calls_attempted": calls,
                    },
                ) from None

            try:
                text = (
                    output_path.read_text(encoding="utf-8").strip()
                    if output_path.exists()
                    else ""
                )
            except OSError:
                text = ""
            if not text:
                text = (result.stdout or "").strip()

            refusal_reason = parse_codex_refusal(text) if text else None
            if refusal_reason is not None:
                if is_image_access_refusal(refusal_reason):
                    if image_access_retries < len(_IMAGE_ACCESS_RETRY_DELAYS_SECONDS):
                        delay = _IMAGE_ACCESS_RETRY_DELAYS_SECONDS[image_access_retries]
                        image_access_retries += 1
                        _sleep_with_cancellation(delay, config.cancellation)
                        attempt -= 1  # Long backoff stays outside the attempt budget.
                        continue
                    raise ProviderUnavailable(
                        "The Codex CLI backend persistently lost the staged image "
                        "attachments; the batch can be resumed later.",
                        details={
                            "provider": "codex_cli",
                            "model": model,
                            "description": _single_line(refusal_reason, limit=200),
                            "provider_calls_attempted": calls,
                        },
                    ) from None
                if attempt < _MAX_ATTEMPTS:
                    _sleep_with_cancellation(
                        _RETRY_DELAY_SECONDS * attempt,
                        config.cancellation,
                    )
                    continue
                raise ProviderError(
                    "The Codex CLI model declined the recognition request.",
                    code="PROVIDER_REFUSED_RECOGNITION",
                    details={
                        "provider": "codex_cli",
                        "model": model,
                        "reason": "refusal",
                        "description": _single_line(refusal_reason, limit=200),
                        "provider_calls_attempted": calls,
                    },
                ) from None
            if text:
                return text

            if attempt < _MAX_ATTEMPTS:
                _sleep_with_cancellation(
                    _RETRY_DELAY_SECONDS * attempt,
                    config.cancellation,
                )
                continue
            raise ProviderError(
                "The Codex CLI returned empty recognition content.",
                code="PROVIDER_RESPONSE_INVALID",
                details={
                    "provider": "codex_cli",
                    "model": model,
                    "reason": "empty",
                    "provider_calls_attempted": calls,
                },
            ) from None

    raise ProviderUnavailable(
        "The Codex CLI recognition failed.",
        details={
            "provider": "codex_cli",
            "model": model,
            "provider_calls_attempted": calls,
        },
    ) from None


def _sleep_with_cancellation(seconds: float, cancellation: object | None) -> None:
    deadline = time.monotonic() + seconds
    while True:
        raise_if_cancelled(cancellation)
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            return
        time.sleep(min(remaining, 0.5))


def _single_line(text: str, limit: int = 500) -> str:
    detail = " ".join((text or "").split())
    if len(detail) > limit:
        detail = detail[:limit].rstrip() + "..."
    return detail
