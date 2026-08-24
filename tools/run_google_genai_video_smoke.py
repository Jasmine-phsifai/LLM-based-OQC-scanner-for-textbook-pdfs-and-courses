"""Run one bounded live gate and emit discriminated credential-safe JSON."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
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
    list_google_genai_models,
    recognize_video,
)
from ocrllm.errors import ConfigError, OCRLLMError, VideoError


class _LiveSmokeFailure(Exception):
    """Keep a runner stage beside, not inside, a public product error."""

    def __init__(self, stage: str, error: OCRLLMError | None) -> None:
        self.stage = stage
        self.error = error
        super().__init__(stage)


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse one explicit model, controlled short MP4 fixture, and timeout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=120.0)
    return parser.parse_args(argv)


def run_google_genai_video_smoke(arguments: argparse.Namespace) -> dict[str, object]:
    """Discover the catalog, run video orchestration, and retain safe evidence."""
    try:
        models = list_google_genai_models(
            GoogleGenAISettings(),
            arguments.timeout,
        )
    except OCRLLMError as error:
        raise _LiveSmokeFailure("catalog", error) from None
    except Exception:
        raise _LiveSmokeFailure("catalog", None) from None
    if arguments.model not in models:
        raise _LiveSmokeFailure(
            "model_selection",
            ConfigError(
                "The requested Google model is absent from the current catalog.",
                code="CONFIG_INVALID",
            ),
        ) from None

    try:
        with tempfile.TemporaryDirectory(
            prefix="ocrllm-google-video-smoke-"
        ) as temporary_root:
            outcome = recognize_video(
                arguments.video,
                output_dir=Path(temporary_root) / "output",
                image_config=Config(
                    provider=GoogleGenAISettings(),
                    vision_model=VisionModelSettings(name=arguments.model),
                    timeout_seconds=arguments.timeout,
                ),
                audio_config=Config(
                    provider=GoogleGenAISettings(),
                    audio_model=AudioModelSettings(name=arguments.model),
                    timeout_seconds=arguments.timeout,
                ),
            )
            return _safe_video_summary(
                outcome,
                model=arguments.model,
                catalog_count=len(models),
            )
    except OCRLLMError as error:
        raise _LiveSmokeFailure("video_orchestration", error) from None
    except _LiveSmokeFailure:
        raise
    except Exception:
        raise _LiveSmokeFailure("video_orchestration", None) from None


def _safe_video_summary(
    outcome: Any,
    *,
    model: str,
    catalog_count: int,
) -> dict[str, object]:
    if type(outcome) is not VideoRecognitionOutcome:
        raise ConfigError(
            "Google video smoke returned an unexpected outcome boundary.",
            code="CONFIG_INVALID",
        ) from None
    _validate_owned_artifacts(outcome)

    frames = _safe_frame_summary(outcome, model)
    audio = _safe_audio_summary(outcome, model)
    composition = _safe_composition_summary(outcome, model)
    passed = (
        outcome.status == "complete"
        and frames["status"] == "complete"
        and frames["provider_calls_attempted"] == 1
        and audio["status"] == "recognized"
        and audio["provider_calls_attempted"] == 1
        and composition["status"] == "complete"
    )
    return {
        "report_type": "video_outcome",
        "status": "passed" if passed else "failed",
        "catalog_count": catalog_count,
        "model": model,
        "outcome_status": outcome.status,
        "frames": frames,
        "audio": audio,
        "composition": composition,
    }


def _validate_owned_artifacts(outcome: VideoRecognitionOutcome) -> None:
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
            errors.append(_safe_error(item.error.code, "frame_recognition", count))
    if outcome.frame_error is not None:
        count = _error_call_count(outcome.frame_error)
        call_counts.append(count)
        errors.append(
            _safe_error(outcome.frame_error.code, "frame_recognition", count)
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
) -> dict[str, object]:
    if outcome.audio_result is not None:
        count = _result_call_count(outcome.audio_result, "audio", model)
        return {
            "status": "recognized",
            "artifact_present": True,
            "provider_calls_attempted": count,
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
        "error": _safe_error(outcome.audio_error.code, stage, count),
    }


def _safe_composition_summary(
    outcome: VideoRecognitionOutcome,
    model: str,
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
        model_token_usage = _safe_model_token_usage(result.metadata, model)
        if model_token_usage:
            summary["model_token_usage"] = model_token_usage
        return summary
    except OCRLLMError as error:
        return {
            "status": "failed",
            "asset_count": 0,
            "error": _safe_error(error.code, "composition", 0),
        }
    except Exception:
        return {
            "status": "failed",
            "asset_count": 0,
            "error": _safe_error("UNEXPECTED_SAFE_FAILURE", "composition", 0),
        }


def _safe_model_token_usage(
    metadata: Mapping[str, object],
    model: str,
) -> list[dict[str, object]]:
    usage = metadata.get("current_model_token_usage")
    if usage is None:
        return []
    if type(usage) is not tuple:
        raise ConfigError(
            "Google video smoke returned invalid model-usage evidence.",
            code="CONFIG_INVALID",
        ) from None

    safe_usage: list[dict[str, object]] = []
    for item in usage:
        if not isinstance(item, Mapping):
            raise ConfigError(
                "Google video smoke returned invalid model-usage evidence.",
                code="CONFIG_INVALID",
            ) from None
        input_tokens = item.get("input_tokens")
        output_tokens = item.get("output_tokens")
        if (
            item.get("model") != model
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


def _result_call_count(result: Any, source_type: str, model: str) -> int:
    metadata = result.metadata
    count = metadata.get("provider_call_count")
    if (
        result.source_type != source_type
        or result.output_path is not None
        or metadata.get("provider") != "google"
        or metadata.get("model") != model
        or type(count) is not int
        or count != 1
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


def _safe_error(code: str, stage: str, calls: int | None) -> dict[str, object]:
    return {
        "code": code,
        "stage": stage,
        "provider_calls_attempted": calls,
    }


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    try:
        summary = run_google_genai_video_smoke(arguments)
    except _LiveSmokeFailure as failure:
        if failure.error is None:
            return _report_failure(
                code="UNEXPECTED_SAFE_FAILURE",
                stage=failure.stage,
                calls=None,
            )
        return _report_failure(
            code=failure.error.code,
            stage=failure.stage,
            calls=_error_call_count(failure.error),
        )
    except OCRLLMError as error:
        return _report_failure(
            code=error.code,
            stage=None,
            calls=_error_call_count(error),
        )
    except Exception:
        return _report_failure(
            code="UNEXPECTED_SAFE_FAILURE",
            stage=None,
            calls=None,
        )
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0 if summary["status"] == "passed" else 1


def _report_failure(*, code: str, stage: str | None, calls: int | None) -> int:
    print(
        json.dumps(
            {
                "report_type": "runner_failure",
                "status": "failed",
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


if __name__ == "__main__":
    sys.exit(main())
