"""Repair preflighted merged-image failure markers serially."""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .errors import OutputError, ProviderError
from .imaging.snapshot_image_group import snapshot_image_group
from .output.write_markdown_atomically import write_markdown_atomically
from .parse_merged_image_failure_markers import MergedImageFailureMarker
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
from .providers.recognize_provider_model_images import (
    recognize_provider_model_images,
)
from .providers.vision_provider_response import VisionProviderResponse
from .result import RecognitionResult


def repair_marked_image_batches(
    batches: tuple[tuple[Path, ...], ...],
    *,
    markers: tuple[MergedImageFailureMarker, ...],
    markdown: str,
    provider_lanes: tuple[tuple[ProviderModel, ...], ...],
    prompt: str,
    image_task: str,
    output_path: Path,
    config: Config,
) -> RecognitionResult:
    """Dispatch only marked absolute slots and publish every paid success."""
    lane_starts = [0] * len(provider_lanes)
    usage: tuple[ProviderModelUsage, ...] = ()
    usage_order = build_provider_model_usage_order(
        provider_lanes,
        slot_count=len(batches),
    )
    provider_failures: list[dict[str, int | str]] = []
    failed_slots: list[dict[str, int | str]] = []
    repaired_slot_count = 0
    provider_cleanup_failure = False
    snapshot_cleanup_failure = False

    for marker in markers:
        lane_index = marker.slot_index % len(provider_lanes)
        lane = provider_lanes[lane_index]
        slot_failures: list[dict[str, int | str]] = []
        publication_succeeded = False
        provider_succeeded = False
        try:
            with snapshot_image_group(
                batches[marker.slot_index],
                config=config,
            ) as snapshots:
                for offset in range(len(lane)):
                    provider_index = (lane_starts[lane_index] + offset) % len(lane)
                    candidate = lane[provider_index]
                    try:
                        response = recognize_provider_model_images(
                            candidate,
                            snapshots,
                            prompt=prompt,
                            timeout_seconds=config.timeout_seconds,
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

                    provider_succeeded = True
                    if type(response) is VisionProviderResponse:
                        repaired_markdown = response.markdown
                        input_tokens = response.input_tokens
                        output_tokens = response.output_tokens
                        provider_cleanup_failure = (
                            provider_cleanup_failure or not response.client_closed
                        )
                    else:
                        repaired_markdown = response
                        input_tokens = None
                        output_tokens = None
                    usage = add_provider_model_usage(
                        usage,
                        provider=candidate,
                        calls=1,
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
                    provider_failures.extend(slot_failures)
                    lane_starts[lane_index] = provider_index
                    break
        except OutputError as error:
            if publication_succeeded or (
                not provider_succeeded and len(slot_failures) == len(lane)
            ):
                snapshot_cleanup_failure = True
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
            "Image repair completed after one or more provider candidates failed."
        )
    if failed_slots:
        warnings.append("One or more image slots remain failed after repair.")
    if provider_cleanup_failure:
        warnings.append(
            "At least one provider client could not be closed during image repair."
        )
    if snapshot_cleanup_failure:
        warnings.append(
            "At least one temporary image snapshot could not be removed after repair."
        )

    metadata: dict[str, object] = {
        "slot_count": len(batches),
        "repair_marker_count": len(markers),
        "repaired_slot_count": repaired_slot_count,
        "settled_slot_count": len(batches) - len(failed_slots),
        "provider_call_count": sum(row.calls for row in usage),
        "current_provider_model_usage": provider_model_usage_documents(usage),
    }
    if failed_slots:
        metadata["failed_slots"] = tuple(failed_slots)
    if provider_failures:
        metadata["provider_failures"] = tuple(provider_failures)
    return RecognitionResult(
        markdown=markdown,
        source_type="image",
        profile=image_task,
        status="partial" if failed_slots else "complete",
        output_path=output_path,
        warnings=tuple(warnings),
        metadata=metadata,
    )
