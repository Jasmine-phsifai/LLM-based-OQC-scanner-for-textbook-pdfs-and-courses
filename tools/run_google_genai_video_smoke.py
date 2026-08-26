"""Run one bounded live gate and emit discriminated credential-safe JSON."""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ocrllm import (
    AudioModelSettings,
    Config,
    GoogleGenAISettings,
    VideoRecognitionOutcome,
    VisionModelSettings,
    compose_video_result,
    extract_video_frames,
    list_google_genai_models,
    recognize_video,
)
from ocrllm.errors import ConfigError, OCRLLMError, VideoError
from ocrllm.recognize_video_frames import _VIDEO_FRAME_GROUP_LIMIT


_SAFE_PROVIDER_FAILURE_REASONS = frozenset(
    {
        "empty",
        "invalid_encoding",
        "invalid_no_speech_marker",
        "missing_text",
        "refusal",
    }
)
_SAFE_FAILURE_SCOPES = frozenset(
    {"credential", "model", "provider", "request", "response"}
)
_SAFE_PROVIDER_STATUSES = frozenset(
    {
        "ABORTED",
        "ALREADY_EXISTS",
        "CANCELLED",
        "DATA_LOSS",
        "DEADLINE_EXCEEDED",
        "FAILED_PRECONDITION",
        "INTERNAL",
        "INVALID_ARGUMENT",
        "NOT_FOUND",
        "OUT_OF_RANGE",
        "PERMISSION_DENIED",
        "RESOURCE_EXHAUSTED",
        "UNAUTHENTICATED",
        "UNAVAILABLE",
        "UNIMPLEMENTED",
        "UNKNOWN",
    }
)
_SAFE_LIFECYCLE_DETAIL_NAMES = (
    "remote_file_deleted",
    "provider_file_cleanup_failed",
    "provider_client_closed",
    "provider_client_cleanup_failed",
)
_SAFE_PROVIDER_OPERATIONS = frozenset(
    {"client_setup", "catalog", "upload", "processing", "generation"}
)


class _LiveSmokeFailure(Exception):
    """Keep a runner stage beside, not inside, a public product error."""

    def __init__(self, stage: str, error: OCRLLMError | None) -> None:
        self.stage = stage
        self.error = error
        super().__init__(stage)


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse explicit branch models, controlled short MP4 fixture, and timeout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-model", required=True)
    parser.add_argument("--audio-model", required=True)
    parser.add_argument(
        "--expected-audio-transport",
        required=True,
        choices=("google_inline", "google_files"),
    )
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument(
        "--expected-frame-groups",
        required=True,
        type=int,
        choices=(1, 2),
        dest="expected_frame_group_count",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--audio-interval-minutes", type=_positive_integer)
    parser.add_argument("--expected-audio-calls", type=_positive_integer)
    parser.add_argument("--output-dir", type=Path)
    arguments = parser.parse_args(argv)
    interval_values = (
        arguments.audio_interval_minutes,
        arguments.expected_audio_calls,
        arguments.output_dir,
    )
    if any(value is not None for value in interval_values) and not all(
        value is not None for value in interval_values
    ):
        parser.error(
            "--audio-interval-minutes, --expected-audio-calls, and "
            "--output-dir must be used together"
        )
    if (
        arguments.audio_interval_minutes is not None
        and arguments.expected_audio_transport != "google_files"
    ):
        parser.error("video audio intervals require google_files transport")
    return arguments


def _positive_integer(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if value <= 0 or str(value) != raw:
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    return value


def run_google_genai_video_smoke(arguments: argparse.Namespace) -> dict[str, object]:
    """Discover the catalog, run video orchestration, and retain safe evidence."""
    try:
        preflight_retained_count, preflight_group_count = _preflight_video_frames(
            arguments.video
        )
    except OCRLLMError as error:
        raise _LiveSmokeFailure("video_preflight", error) from None
    except Exception:
        raise _LiveSmokeFailure("video_preflight", None) from None
    if preflight_group_count != arguments.expected_frame_group_count:
        raise _LiveSmokeFailure(
            "video_preflight",
            ConfigError(
                "The controlled video does not match the expected frame-group count.",
                code="CONFIG_INVALID",
                details={"provider_calls_attempted": 0},
            ),
        ) from None

    try:
        models = list_google_genai_models(
            GoogleGenAISettings(),
            arguments.timeout,
        )
    except OCRLLMError as error:
        raise _LiveSmokeFailure("catalog", error) from None
    except Exception:
        raise _LiveSmokeFailure("catalog", None) from None
    for model in (arguments.image_model, arguments.audio_model):
        if model not in models:
            raise _LiveSmokeFailure(
                "model_selection",
                ConfigError(
                    "A requested Google model is absent from the current catalog.",
                    code="CONFIG_INVALID",
                ),
            ) from None

    try:
        if arguments.audio_interval_minutes is not None:
            return _run_video_recognition(
                arguments,
                output_dir=arguments.output_dir,
                catalog_count=len(models),
                preflight_retained_count=preflight_retained_count,
            )
        with tempfile.TemporaryDirectory(
            prefix="ocrllm-google-video-smoke-"
        ) as temporary_root:
            return _run_video_recognition(
                arguments,
                output_dir=Path(temporary_root) / "output",
                catalog_count=len(models),
                preflight_retained_count=preflight_retained_count,
            )
    except OCRLLMError as error:
        raise _LiveSmokeFailure("video_orchestration", error) from None
    except _LiveSmokeFailure:
        raise
    except Exception:
        raise _LiveSmokeFailure("video_orchestration", None) from None


def _run_video_recognition(
    arguments: argparse.Namespace,
    *,
    output_dir: Path,
    catalog_count: int,
    preflight_retained_count: int,
) -> dict[str, object]:
    video_options: dict[str, object] = {}
    if arguments.audio_interval_minutes is not None:
        video_options["audio_interval_minutes"] = arguments.audio_interval_minutes
    outcome = recognize_video(
        arguments.video,
        output_dir=output_dir,
        image_config=Config(
            provider=GoogleGenAISettings(),
            vision_model=VisionModelSettings(name=arguments.image_model),
            timeout_seconds=arguments.timeout,
        ),
        audio_config=Config(
            provider=GoogleGenAISettings(),
            audio_model=AudioModelSettings(name=arguments.audio_model),
            timeout_seconds=arguments.timeout,
        ),
        **video_options,
    )
    expected_audio_calls = arguments.expected_audio_calls
    if expected_audio_calls is None:
        expected_audio_calls = 1
    return _safe_video_summary(
        outcome,
        image_model=arguments.image_model,
        audio_model=arguments.audio_model,
        expected_audio_transport=arguments.expected_audio_transport,
        expected_audio_calls=expected_audio_calls,
        audio_interval_minutes=arguments.audio_interval_minutes,
        catalog_count=catalog_count,
        preflight_retained_count=preflight_retained_count,
        expected_frame_group_count=arguments.expected_frame_group_count,
    )


def _preflight_video_frames(source: Path) -> tuple[int, int]:
    """Count the controlled fixture's groups before any provider request."""
    with tempfile.TemporaryDirectory(
        prefix="ocrllm-google-video-preflight-"
    ) as temporary_root:
        frames = extract_video_frames(
            source,
            output_dir=Path(temporary_root) / "output",
        )
        retained_count = len(frames)
    group_count = (
        retained_count + _VIDEO_FRAME_GROUP_LIMIT - 1
    ) // _VIDEO_FRAME_GROUP_LIMIT
    return retained_count, group_count


def _safe_video_summary(
    outcome: Any,
    *,
    image_model: str,
    audio_model: str,
    expected_audio_transport: str,
    expected_audio_calls: int = 1,
    audio_interval_minutes: int | None = None,
    catalog_count: int,
    preflight_retained_count: int,
    expected_frame_group_count: int,
) -> dict[str, object]:
    if type(outcome) is not VideoRecognitionOutcome:
        raise ConfigError(
            "Google video smoke returned an unexpected outcome boundary.",
            code="CONFIG_INVALID",
        ) from None
    _validate_owned_artifacts(
        outcome,
        require_audio_state_removed=(
            audio_interval_minutes is not None and outcome.status == "complete"
        ),
    )

    frames = _safe_frame_summary(outcome, image_model)
    audio = _safe_audio_summary(
        outcome,
        audio_model,
        expected_audio_transport,
        expected_calls=expected_audio_calls,
        interval_minutes=audio_interval_minutes,
    )
    composition = _safe_composition_summary(
        outcome,
        expected_models=(image_model, audio_model),
    )
    passed = (
        outcome.status == "complete"
        and frames["status"] == "complete"
        and frames["retained_count"] == preflight_retained_count
        and frames["group_count"] == expected_frame_group_count
        and frames["provider_calls_attempted"] == expected_frame_group_count
        and audio["status"] == "recognized"
        and audio["provider_calls_attempted"] == expected_audio_calls
        and audio["transport"] == expected_audio_transport
        and audio["provider_client_closed"] is True
        and (
            expected_audio_transport != "google_files"
            or audio["remote_file_deleted"] is True
        )
        and composition["status"] == "complete"
    )
    preflight: dict[str, object] = {
        "retained_count": preflight_retained_count,
        "expected_frame_group_count": expected_frame_group_count,
    }
    if audio_interval_minutes is not None:
        preflight["audio_interval_minutes"] = audio_interval_minutes
        preflight["expected_audio_calls"] = expected_audio_calls
    return {
        "report_type": "video_outcome",
        "status": "passed" if passed else "failed",
        "catalog_count": catalog_count,
        "image_model": image_model,
        "audio_model": audio_model,
        "outcome_status": outcome.status,
        "preflight": preflight,
        "frames": frames,
        "audio": audio,
        "composition": composition,
    }


def _validate_owned_artifacts(
    outcome: VideoRecognitionOutcome,
    *,
    require_audio_state_removed: bool = False,
) -> None:
    if not outcome.output_root.is_dir() or any(
        not frame.path.is_file() for frame in outcome.retained_frames
    ):
        raise ConfigError(
            "Google video smoke did not retain its frame artifacts.",
            code="CONFIG_INVALID",
        ) from None
    if outcome.audio_artifact is not None and not outcome.audio_artifact.is_file():
        raise ConfigError(
            "Google video smoke did not retain its audio artifact.",
            code="CONFIG_INVALID",
        ) from None
    if require_audio_state_removed and (
        outcome.output_root / ".ocrllm-video-audio-resume.json"
    ).exists():
        raise ConfigError(
            "Google video smoke retained temporary state after success.",
            code="CONFIG_INVALID",
        ) from None
    if (outcome.output_root / "audio" / "result.md").exists() or (
        outcome.output_root / "result.md"
    ).exists():
        raise ConfigError(
            "Google video smoke retained a nested publication.",
            code="CONFIG_INVALID",
        ) from None


def _safe_frame_summary(
    outcome: VideoRecognitionOutcome,
    model: str,
) -> dict[str, object]:
    errors: list[dict[str, object]] = []
    call_counts: list[int | None] = []
    successful_groups = 0

    for item in outcome.frame_outcomes:
        if item.result is not None:
            successful_groups += 1
            call_counts.append(_result_call_count(item.result, "image", model))
        else:
            assert item.error is not None
            count = _error_call_count(item.error)
            call_counts.append(count)
            errors.append(_safe_error(item.error, "frame_recognition", count))
    if outcome.frame_error is not None:
        count = _error_call_count(outcome.frame_error)
        call_counts.append(count)
        errors.append(
            _safe_error(outcome.frame_error, "frame_recognition", count)
        )

    if successful_groups == len(outcome.frame_outcomes) and successful_groups:
        status = "complete"
    elif successful_groups:
        status = "partial"
    else:
        status = "failed"
    return {
        "status": status,
        "retained_count": len(outcome.retained_frames),
        "group_count": len(outcome.frame_outcomes),
        "successful_group_count": successful_groups,
        "provider_calls_attempted": _sum_known_call_counts(call_counts),
        "errors": errors,
    }


def _safe_audio_summary(
    outcome: VideoRecognitionOutcome,
    model: str,
    expected_transport: str,
    *,
    expected_calls: int = 1,
    interval_minutes: int | None = None,
) -> dict[str, object]:
    if outcome.audio_result is not None:
        count = _result_call_count(
            outcome.audio_result,
            "audio",
            model,
            expected_count=expected_calls,
        )
        metadata = outcome.audio_result.metadata
        duration_seconds = metadata.get("duration_seconds")
        client_closed = metadata.get("provider_client_closed")
        transport = metadata.get("transport")
        if (
            isinstance(duration_seconds, bool)
            or not isinstance(duration_seconds, (int, float))
            or duration_seconds <= 0
            or type(client_closed) is not bool
        ):
            raise ConfigError(
                "Google video smoke returned invalid audio lifecycle evidence.",
                code="CONFIG_INVALID",
            ) from None
        if expected_transport == "google_files":
            remote_file_deleted = metadata.get("remote_file_deleted")
            if (
                transport != "google_files"
                or duration_seconds <= 300
                or type(remote_file_deleted) is not bool
            ):
                raise ConfigError(
                    "Google video smoke returned unexpected Files audio evidence.",
                    code="CONFIG_INVALID",
                ) from None
            if interval_minutes is not None and math.ceil(
                duration_seconds / (interval_minutes * 60)
            ) != expected_calls:
                raise ConfigError(
                    "Google video smoke returned unexpected interval call evidence.",
                    code="CONFIG_INVALID",
                ) from None
        else:
            remote_file_deleted = None
            if transport is not None or duration_seconds > 300:
                raise ConfigError(
                    "Google video smoke returned unexpected inline audio evidence.",
                    code="CONFIG_INVALID",
                ) from None
        return {
            "status": "recognized",
            "artifact_present": True,
            "provider_calls_attempted": count,
            "transport": expected_transport,
            "duration_seconds": float(duration_seconds),
            "remote_file_deleted": remote_file_deleted,
            "provider_client_closed": client_closed,
            "error": None,
        }

    assert outcome.audio_error is not None
    if outcome.audio_artifact is None:
        if not isinstance(outcome.audio_error, VideoError):
            raise ConfigError(
                "Google video smoke returned inconsistent audio failure evidence.",
                code="CONFIG_INVALID",
            ) from None
        count: int | None = 0
        stage = "video_extract_audio"
    else:
        count = _error_call_count(outcome.audio_error)
        stage = "audio_recognition"
    return {
        "status": outcome.audio_state,
        "artifact_present": outcome.audio_artifact is not None,
        "provider_calls_attempted": count,
        "error": _safe_error(outcome.audio_error, stage, count),
    }


def _safe_composition_summary(
    outcome: VideoRecognitionOutcome,
    expected_models: tuple[str, str],
) -> dict[str, object]:
    if outcome.status == "failed":
        return {"status": "not_started", "asset_count": 0, "error": None}
    try:
        result = compose_video_result(outcome)
        if (
            result.source_type != "video"
            or result.output_path is not None
            or result.status != outcome.status
        ):
            raise ConfigError(
                "Google video smoke returned an unexpected composition boundary.",
                code="CONFIG_INVALID",
            ) from None
        summary: dict[str, object] = {
            "status": result.status,
            "asset_count": len(result.assets),
            "error": None,
        }
        model_token_usage = _safe_model_token_usage(result.metadata, expected_models)
        if model_token_usage:
            summary["model_token_usage"] = model_token_usage
        return summary
    except OCRLLMError as error:
        return {
            "status": "failed",
            "asset_count": 0,
            "error": _safe_error(error, "composition", 0),
        }
    except Exception:
        return {
            "status": "failed",
            "asset_count": 0,
            "error": _safe_error("UNEXPECTED_SAFE_FAILURE", "composition", 0),
        }


def _safe_model_token_usage(
    metadata: Mapping[str, object],
    expected_models: tuple[str, str],
) -> list[dict[str, object]]:
    usage = metadata.get("current_model_token_usage")
    if usage is None:
        return []
    if type(usage) is not tuple:
        raise ConfigError(
            "Google video smoke returned invalid model-usage evidence.",
            code="CONFIG_INVALID",
        ) from None

    allowed_models = frozenset(expected_models)
    safe_usage: list[dict[str, object]] = []
    for item in usage:
        if not isinstance(item, Mapping):
            raise ConfigError(
                "Google video smoke returned invalid model-usage evidence.",
                code="CONFIG_INVALID",
            ) from None
        input_tokens = item.get("input_tokens")
        output_tokens = item.get("output_tokens")
        model = item.get("model")
        if (
            type(model) is not str
            or model not in allowed_models
            or type(input_tokens) is not int
            or input_tokens < 0
            or type(output_tokens) is not int
            or output_tokens < 0
        ):
            raise ConfigError(
                "Google video smoke returned invalid model-usage evidence.",
                code="CONFIG_INVALID",
            ) from None
        safe_usage.append(
            {
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        )
    return safe_usage


def _result_call_count(
    result: Any,
    source_type: str,
    model: str,
    *,
    expected_count: int = 1,
) -> int:
    metadata = result.metadata
    count = metadata.get("provider_call_count")
    if (
        result.source_type != source_type
        or result.output_path is not None
        or metadata.get("provider") != "google"
        or metadata.get("model") != model
        or type(count) is not int
        or count != expected_count
    ):
        raise ConfigError(
            "Google video smoke returned invalid provider-call evidence.",
            code="CONFIG_INVALID",
        ) from None
    return count


def _error_call_count(error: OCRLLMError) -> int | None:
    count = error.details.get("provider_calls_attempted")
    if type(count) is int and count >= 0:
        return count
    return None


def _sum_known_call_counts(counts: list[int | None]) -> int | None:
    if any(count is None for count in counts):
        return None
    return sum(count for count in counts if count is not None)


def _safe_error(
    error: OCRLLMError | str,
    stage: str,
    calls: int | None,
) -> dict[str, object]:
    code = error.code if isinstance(error, OCRLLMError) else error
    summary: dict[str, object] = {
        "code": code,
        "stage": stage,
        "provider_calls_attempted": calls,
    }
    if isinstance(error, OCRLLMError):
        reason = error.details.get("reason")
        if type(reason) is str and reason in _SAFE_PROVIDER_FAILURE_REASONS:
            summary["reason"] = reason
        failure_scope = error.details.get("failure_scope")
        if type(failure_scope) is str and failure_scope in _SAFE_FAILURE_SCOPES:
            summary["failure_scope"] = failure_scope
        http_status = error.details.get("http_status")
        if type(http_status) is int and 100 <= http_status <= 599:
            summary["http_status"] = http_status
        provider_status = error.details.get("provider_status")
        if (
            type(provider_status) is str
            and provider_status in _SAFE_PROVIDER_STATUSES
        ):
            summary["provider_status"] = provider_status
        for detail_name in _SAFE_LIFECYCLE_DETAIL_NAMES:
            detail_value = error.details.get(detail_name)
            if type(detail_value) is bool:
                summary[detail_name] = detail_value
        persisted_count = error.details.get("persisted_interval_count")
        if type(persisted_count) is int and persisted_count >= 0:
            summary["persisted_interval_count"] = persisted_count
        operation = error.details.get("provider_operation")
        if type(operation) is str and operation in _SAFE_PROVIDER_OPERATIONS:
            summary["operation"] = operation
        sdk_type = error.details.get("provider_sdk_type")
        if (
            type(sdk_type) is str
            and sdk_type.isascii()
            and sdk_type.isidentifier()
        ):
            summary["sdk_type"] = sdk_type
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    started_at = time.monotonic()
    try:
        summary = run_google_genai_video_smoke(arguments)
    except _LiveSmokeFailure as failure:
        if failure.error is None:
            return _report_failure(
                code="UNEXPECTED_SAFE_FAILURE",
                stage=failure.stage,
                calls=None,
                started_at=started_at,
            )
        return _report_failure(
            code=failure.error.code,
            stage=failure.stage,
            calls=(
                0
                if failure.stage == "video_preflight"
                else _error_call_count(failure.error)
            ),
            started_at=started_at,
        )
    except OCRLLMError as error:
        return _report_failure(
            code=error.code,
            stage=None,
            calls=_error_call_count(error),
            started_at=started_at,
        )
    except Exception:
        return _report_failure(
            code="UNEXPECTED_SAFE_FAILURE",
            stage=None,
            calls=None,
            started_at=started_at,
        )
    summary["elapsed_seconds"] = _elapsed_seconds(started_at)
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0 if summary["status"] == "passed" else 1


def _report_failure(
    *,
    code: str,
    stage: str | None,
    calls: int | None,
    started_at: float,
) -> int:
    print(
        json.dumps(
            {
                "report_type": "runner_failure",
                "status": "failed",
                "elapsed_seconds": _elapsed_seconds(started_at),
                "error": {
                    "code": code,
                    "stage": stage,
                    "provider_calls_attempted": calls,
                },
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 1


def _elapsed_seconds(started_at: float) -> float:
    """Return stable total runner time without exposing wall-clock metadata."""
    return round(time.monotonic() - started_at, 3)


if __name__ == "__main__":
    sys.exit(main())
