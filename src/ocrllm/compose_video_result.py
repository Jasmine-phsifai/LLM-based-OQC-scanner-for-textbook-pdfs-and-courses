"""Compose settled video branches into one standard recognition result."""

from __future__ import annotations

from .errors import OCRLLMError
from .result import RecognitionResult
from .video_recognition_outcome import VideoRecognitionOutcome


def compose_video_result(outcome: VideoRecognitionOutcome) -> RecognitionResult:
    """Compose one returned video outcome without recognition or publication."""
    from .aggregate_current_model_token_usage import (
        aggregate_current_model_token_usage,
    )
    from .aggregate_model_token_usage import aggregate_model_token_usage
    from .build_recognition_result import build_recognition_result
    from .errors import NoSpeechDetected, VideoError
    from .processor_output import ProcessorOutput
    from .read_video_frame_group_identity import read_video_frame_group_identity

    if type(outcome) is not VideoRecognitionOutcome:
        raise TypeError(
            "compose_video_result() requires an exact VideoRecognitionOutcome"
        ) from None
    if outcome.status == "failed":
        raise ValueError("cannot compose a fully failed video outcome") from None

    sections = ["# Video frames"]
    settled_usage_rows: list[dict[str, str | int | None]] = []
    frame_failures: list[dict[str, object]] = []
    provider_call_counts: list[int | None] = []
    warnings: list[str] = []
    hotwords: list[str] = []
    image_provider_client_cleanup_failed = False

    for item in outcome.frame_outcomes:
        indices, timestamps = read_video_frame_group_identity(item)
        body = [
            f"## Retained frame group {item.index + 1}",
            (
                f"Frame indices: `{_format_values(indices)}`  \n"
                f"Timestamps (seconds): `{_format_values(timestamps)}`"
            ),
        ]
        if item.result is not None:
            body.append(item.result.markdown.strip())
            settled_usage_rows.extend(
                aggregate_current_model_token_usage((item.result,))
            )
            provider_call_counts.append(_result_provider_calls(item.result))
            warnings.extend(item.result.warnings)
            hotwords.extend(item.result.hotwords)
            if item.result.metadata.get("provider_client_closed") is False:
                image_provider_client_cleanup_failed = True
        else:
            assert item.error is not None
            settled_usage_rows.extend(
                aggregate_current_model_token_usage((), (item.error,))
            )
            body.append(f"Recognition error: `{item.error.code}`")
            provider_call_counts.append(_error_provider_calls(item.error))
            warnings.append(
                f"Video frame group {item.index + 1} failed with {item.error.code}."
            )
            frame_failures.append(
                {
                    "index": item.index,
                    "code": item.error.code,
                    "frame_indices": indices,
                    "frame_timestamps_seconds": timestamps,
                }
            )
        sections.append("\n\n".join(body))

    metadata: dict[str, object] = {
        "video_frame_count": len(outcome.retained_frames),
        "video_frame_group_count": len(outcome.frame_outcomes),
        "successful_video_frame_group_count": sum(
            item.succeeded for item in outcome.frame_outcomes
        ),
        "failed_video_frame_group_count": sum(
            not item.succeeded for item in outcome.frame_outcomes
        ),
        "audio_state": outcome.audio_state,
    }
    if image_provider_client_cleanup_failed:
        metadata["image_provider_client_closed"] = False
    if outcome.snapshot_cleanup_error is not None:
        metadata["video_cleanup_error_code"] = (
            outcome.snapshot_cleanup_error.code
        )
        warnings.append(
            "Video source-snapshot cleanup failed with "
            f"{outcome.snapshot_cleanup_error.code}."
        )
    if frame_failures:
        metadata["video_frame_group_errors"] = tuple(frame_failures)
    if outcome.frame_error is not None:
        settled_usage_rows.extend(
            aggregate_current_model_token_usage((), (outcome.frame_error,))
        )
        sections.append(
            "## Frame recognition branch\n\n"
            f"Recognition error: `{outcome.frame_error.code}`"
        )
        metadata["video_frame_error_code"] = outcome.frame_error.code
        provider_call_counts.append(_error_provider_calls(outcome.frame_error))
        warnings.append(
            f"Video frame recognition failed with {outcome.frame_error.code}."
        )

    sections.append("# Video audio")
    if outcome.audio_result is not None:
        sections.append(outcome.audio_result.markdown.strip())
        settled_usage_rows.extend(
            aggregate_current_model_token_usage((outcome.audio_result,))
        )
        provider_call_counts.append(_result_provider_calls(outcome.audio_result))
        warnings.extend(outcome.audio_result.warnings)
        hotwords.extend(outcome.audio_result.hotwords)
        if outcome.audio_result.metadata.get("provider_client_closed") is False:
            metadata["audio_provider_client_closed"] = False
    else:
        assert outcome.audio_error is not None
        audio_provider_calls = _error_provider_calls(outcome.audio_error)
        if (
            audio_provider_calls is None
            and outcome.audio_artifact is None
            and isinstance(outcome.audio_error, VideoError)
        ):
            audio_provider_calls = 0
        provider_call_counts.append(audio_provider_calls)
        if outcome.audio_state == "absent":
            sections.append("No audio stream was present.")
        else:
            settled_usage_rows.extend(
                aggregate_current_model_token_usage((), (outcome.audio_error,))
            )
            sections.append(f"Recognition error: `{outcome.audio_error.code}`")
            metadata["audio_error_code"] = outcome.audio_error.code
            warnings.append(
                f"Video audio recognition failed with {outcome.audio_error.code}."
            )
            if (
                isinstance(outcome.audio_error, NoSpeechDetected)
                and outcome.audio_error.details.get("provider_client_closed")
                is False
            ):
                metadata["audio_provider_client_closed"] = False
                cleanup_warning = (
                    "The Google GenAI client could not be closed after recognition."
                )
                if cleanup_warning not in warnings:
                    warnings.append(cleanup_warning)

    known_provider_call_counts = [
        count for count in provider_call_counts if count is not None
    ]
    metadata["current_run_provider_call_count"] = (
        sum(known_provider_call_counts)
        if len(known_provider_call_counts) == len(provider_call_counts)
        else None
    )
    token_usage = aggregate_model_token_usage(settled_usage_rows)
    if token_usage:
        metadata["current_model_token_usage"] = token_usage

    assets = tuple(frame.path for frame in outcome.retained_frames)
    if outcome.audio_artifact is not None:
        assets += (outcome.audio_artifact,)
    return build_recognition_result(
        ProcessorOutput(
            media_type="video",
            markdown="\n\n".join(sections) + "\n",
            status=outcome.status,
            assets=assets,
            hotwords=tuple(hotwords),
            warnings=tuple(warnings),
            metadata=metadata,
        ),
        output_path=None,
    )


def _format_values(values: tuple[int, ...] | tuple[float, ...]) -> str:
    return ", ".join(str(value) for value in values)


def _result_provider_calls(result: RecognitionResult) -> int | None:
    if "current_run_provider_call_count" in result.metadata:
        count = result.metadata["current_run_provider_call_count"]
        if type(count) is int and count >= 0:
            return count
        return None
    count = result.metadata.get("provider_call_count")
    if type(count) is int and count >= 0:
        return count
    return None


def _error_provider_calls(error: OCRLLMError) -> int | None:
    count = error.details.get("provider_calls_attempted")
    if type(count) is int and count >= 0:
        return count
    return None
