"""Repair preflighted merged-audio failure ranges serially."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .audio.build_long_audio_interval_prompt import (
    build_long_audio_interval_prompt,
)
from .audio.build_long_audio_interval_upload_snapshot import (
    build_long_audio_interval_upload_snapshot,
)
from .audio.materialize_long_audio_interval import materialize_long_audio_interval
from .audio.snapshot_long_mp3 import LongMP3Snapshot
from .config import Config
from .errors import NoSpeechDetected, OutputError, ProviderError
from .output.write_markdown_atomically import write_markdown_atomically
from .parse_merged_audio_failure_markers import MergedAudioFailureMarker
from .provider_failure_evidence import (
    bounded_provider_failure_description,
    provider_cleanup_failed,
    provider_failure_usage,
)
from .provider_model_usage import (
    ProviderModelUsage,
    add_provider_model_usage,
    attach_current_provider_model_usage,
    build_provider_model_usage_order,
    provider_model_usage_documents,
)
from .providers.provider_model import ProviderModel
from .providers.recognize_provider_model_audio import recognize_provider_model_audio
from .result import RecognitionResult


def repair_marked_audio_ranges(
    *,
    snapshot: LongMP3Snapshot,
    slot_count: int,
    markers: tuple[MergedAudioFailureMarker, ...],
    markdown: str,
    provider_lanes: tuple[tuple[ProviderModel, ...], ...],
    output_path: Path,
    config: Config,
) -> RecognitionResult:
    """Dispatch only marked ranges and publish every speech/no-speech success."""
    lane_starts = [0] * len(provider_lanes)
    usage: tuple[ProviderModelUsage, ...] = ()
    usage_order = build_provider_model_usage_order(
        provider_lanes,
        slot_count=slot_count,
    )
    provider_failures: list[dict[str, int | str]] = []
    failed_slots: list[dict[str, int | str]] = []
    repaired_slot_count = 0
    no_speech_repaired_slot_count = 0
    provider_cleanup_failure = False
    interval_cleanup_failure = False

    for marker in markers:
        lane_index = marker.slot_index % len(provider_lanes)
        lane = provider_lanes[lane_index]
        slot_failures: list[dict[str, int | str]] = []
        publication_succeeded = False
        provider_succeeded = False
        try:
            with _materialized_request(snapshot, marker) as request_snapshot:
                prompt = build_long_audio_interval_prompt(marker.window)
                for offset in range(len(lane)):
                    provider_index = (lane_starts[lane_index] + offset) % len(lane)
                    candidate = lane[provider_index]
                    no_speech = False
                    try:
                        response = recognize_provider_model_audio(
                            candidate,
                            request_snapshot,
                            prompt=prompt,
                            transport="files",
                            timeout_seconds=config.timeout_seconds,
                        )
                    except NoSpeechDetected as error:
                        provider_succeeded = True
                        no_speech = True
                        calls, input_tokens, output_tokens = provider_failure_usage(
                            error
                        )
                        provider_cleanup_failure = (
                            provider_cleanup_failure
                            or provider_cleanup_failed(error)
                        )
                        repaired_markdown = (
                            "<!-- OCRLLM_NO_SPEECH_AUDIO_SLOT "
                            f"index={marker.slot_index + 1} -->"
                        )
                    except ProviderError as error:
                        calls, input_tokens, output_tokens = provider_failure_usage(
                            error
                        )
                        usage = add_provider_model_usage(
                            usage,
                            provider=candidate,
                            calls=calls,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            usage_order=usage_order,
                        )
                        provider_cleanup_failure = (
                            provider_cleanup_failure
                            or provider_cleanup_failed(error)
                        )
                        slot_failures.append(
                            {
                                "slot_index": marker.slot_index,
                                "vendor": candidate.vendor,
                                "model": candidate.model,
                                "code": error.code,
                                "description": bounded_provider_failure_description(
                                    error
                                ),
                            }
                        )
                        continue
                    else:
                        provider_succeeded = True
                        calls = 1
                        input_tokens = response.input_tokens
                        output_tokens = response.output_tokens
                        repaired_markdown = response.markdown
                        provider_cleanup_failure = provider_cleanup_failure or (
                            not response.client_closed
                            or not response.remote_file_deleted
                        )

                    usage = add_provider_model_usage(
                        usage,
                        provider=candidate,
                        calls=calls,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        usage_order=usage_order,
                    )
                    updated_markdown = markdown.replace(
                        marker.comment,
                        repaired_markdown.strip(),
                        1,
                    )
                    try:
                        write_markdown_atomically(
                            output_path,
                            updated_markdown,
                            overwrite=True,
                        )
                    except OutputError as error:
                        attach_current_provider_model_usage(error, usage)
                        raise
                    markdown = updated_markdown
                    publication_succeeded = True
                    repaired_slot_count += 1
                    if no_speech:
                        no_speech_repaired_slot_count += 1
                    provider_failures.extend(slot_failures)
                    lane_starts[lane_index] = provider_index
                    break
        except OutputError as error:
            if publication_succeeded or (
                not provider_succeeded and len(slot_failures) == len(lane)
            ):
                interval_cleanup_failure = True
            else:
                attach_current_provider_model_usage(error, usage)
                raise

        if not publication_succeeded:
            failed = slot_failures[-1]
            failed_slots.append(
                {
                    "slot_index": failed["slot_index"],
                    "provider": failed["vendor"],
                    "model": failed["model"],
                    "code": failed["code"],
                    "description": failed["description"],
                }
            )

    warnings: list[str] = []
    if provider_failures:
        warnings.append(
            "Audio repair completed after one or more provider candidates failed."
        )
    if failed_slots:
        warnings.append("One or more audio slots remain failed after repair.")
    if provider_cleanup_failure:
        warnings.append(
            "At least one provider audio upload or client could not be cleaned up "
            "during repair."
        )
    if interval_cleanup_failure:
        warnings.append(
            "At least one temporary audio interval could not be removed after repair."
        )

    metadata: dict[str, object] = {
        "slot_count": slot_count,
        "repair_marker_count": len(markers),
        "repaired_slot_count": repaired_slot_count,
        "no_speech_repaired_slot_count": no_speech_repaired_slot_count,
        "settled_slot_count": slot_count - len(failed_slots),
        "provider_call_count": sum(row.calls for row in usage),
        "current_provider_model_usage": provider_model_usage_documents(usage),
        "duration_seconds": snapshot.duration_seconds,
        "byte_size": snapshot.byte_size,
    }
    if failed_slots:
        metadata["failed_slots"] = tuple(failed_slots)
    if provider_failures:
        metadata["provider_failures"] = tuple(provider_failures)
    return RecognitionResult(
        markdown=markdown,
        source_type="audio",
        status="partial" if failed_slots else "complete",
        output_path=output_path,
        warnings=tuple(warnings),
        metadata=metadata,
    )


@contextmanager
def _materialized_request(
    snapshot: LongMP3Snapshot,
    marker: MergedAudioFailureMarker,
) -> Iterator[LongMP3Snapshot]:
    with materialize_long_audio_interval(
        snapshot.path,
        window=marker.window,
    ) as segment:
        yield build_long_audio_interval_upload_snapshot(
            segment,
            duration_seconds=(
                marker.window.actual_end_seconds
                - marker.window.actual_start_seconds
            ),
        )
