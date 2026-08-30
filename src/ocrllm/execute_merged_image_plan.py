"""Execute unresolved merged-image slots through one scalar provider."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

from .config import Config
from .errors import OCRLLMError, OutputError, ProviderError, ResumeStateError
from .fingerprint_image_sources import fingerprint_image_sources
from .imaging.snapshot_image_group import snapshot_image_group
from .merged_image_resume_state import MergedImageResumeState, MergedImageSlot
from .output.save_merged_image_resume_state_atomically import (
    save_merged_image_resume_state_atomically,
)
from .providers.provider_model import ProviderModel
from .provider_model_usage import ProviderModelUsage
from .providers.recognize_provider_model_images import (
    recognize_provider_model_images,
)
from .providers.vision_provider_response import VisionProviderResponse


_MAX_PROVIDER_FAILURE_DESCRIPTION_CHARS = 512


def execute_merged_image_plan(
    state: MergedImageResumeState,
    batches: tuple[tuple[Path, ...], ...],
    *,
    provider_lane: tuple[ProviderModel, ...],
    prompt: str,
    state_path: Path,
    timeout_seconds: float,
) -> tuple[
    MergedImageResumeState,
    tuple[ProviderModelUsage, ...],
    int,
    tuple[dict[str, int | str], ...],
]:
    """Settle each unresolved slot through one serial fallback lane."""
    current_usage: tuple[ProviderModelUsage, ...] = ()
    reused_slot_count = 0
    provider_failures: list[dict[str, int | str]] = []
    last_success_index = 0
    for slot, batch in zip(state.slots, batches, strict=True):
        if slot.status == "settled":
            reused_slot_count += 1
            continue
        with snapshot_image_group(batch, config=Config()) as snapshots:
            actual_sources = fingerprint_image_sources(batch, snapshots)
            expected_sources = tuple(state.sources[index] for index in slot.source_indexes)
            if actual_sources != expected_sources:
                raise ResumeStateError(
                    "An image source changed after the merged plan was validated.",
                    code="RESUME_STATE_MISMATCH",
                    details={"provider_calls_attempted": 0},
                ) from None
            slot_failures: list[dict[str, int | str]] = []
            for offset in range(len(provider_lane)):
                provider_index = (last_success_index + offset) % len(provider_lane)
                provider = provider_lane[provider_index]
                try:
                    response = recognize_provider_model_images(
                        provider,
                        snapshots,
                        prompt=prompt,
                        timeout_seconds=timeout_seconds,
                    )
                except ProviderError as error:
                    calls, input_tokens, output_tokens = _usage_from_error(error)
                    description = _bounded_error_description(error)
                    failed_slot = MergedImageSlot(
                        index=slot.index,
                        source_indexes=slot.source_indexes,
                        status="failed",
                        vendor=provider.vendor,
                        model=provider.model,
                        error_code=error.code,
                        error_description=description,
                    )
                    state, current_usage = _checkpoint_outcome(
                        state,
                        failed_slot,
                        provider=provider,
                        calls=calls,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cleanup_failed=_cleanup_failed(error),
                        state_path=state_path,
                        current_usage=current_usage,
                    )
                    slot_failures.append(
                        {
                            "slot_index": slot.index,
                            "vendor": provider.vendor,
                            "model": provider.model,
                            "code": error.code,
                            "description": description,
                        }
                    )
                    continue

                if type(response) is VisionProviderResponse:
                    markdown = response.markdown
                    input_tokens = response.input_tokens
                    output_tokens = response.output_tokens
                    cleanup_failed = not response.client_closed
                else:
                    markdown = response
                    input_tokens = None
                    output_tokens = None
                    cleanup_failed = False
                settled_slot = MergedImageSlot(
                    index=slot.index,
                    source_indexes=slot.source_indexes,
                    status="settled",
                    markdown=markdown,
                    markdown_sha256=hashlib.sha256(
                        markdown.encode("utf-8")
                    ).hexdigest(),
                    vendor=provider.vendor,
                    model=provider.model,
                )
                state, current_usage = _checkpoint_outcome(
                    state,
                    settled_slot,
                    provider=provider,
                    calls=1,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cleanup_failed=cleanup_failed,
                    state_path=state_path,
                    current_usage=current_usage,
                )
                provider_failures.extend(slot_failures)
                last_success_index = provider_index
                break
    return state, current_usage, reused_slot_count, tuple(provider_failures)


def _checkpoint_outcome(
    state: MergedImageResumeState,
    outcome: MergedImageSlot,
    *,
    provider: ProviderModel,
    calls: int,
    input_tokens: int | None,
    output_tokens: int | None,
    cleanup_failed: bool,
    state_path: Path,
    current_usage: tuple[ProviderModelUsage, ...],
) -> tuple[MergedImageResumeState, tuple[ProviderModelUsage, ...]]:
    slots = list(state.slots)
    slots[outcome.index] = outcome
    usage = _add_usage(
        state.usage,
        provider=provider,
        calls=calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    current_usage = _add_usage(
        current_usage,
        provider=provider,
        calls=calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    updated = replace(
        state,
        slots=tuple(slots),
        usage=usage,
        provider_cleanup_failed=state.provider_cleanup_failed or cleanup_failed,
    )
    try:
        save_merged_image_resume_state_atomically(state_path, updated)
    except OutputError as error:
        error._add_safe_detail(
            "provider_calls_attempted",
            sum(row.calls for row in current_usage),
        )
        raise
    return updated, current_usage


def _add_usage(
    usage: tuple[ProviderModelUsage, ...],
    *,
    provider: ProviderModel,
    calls: int,
    input_tokens: int | None,
    output_tokens: int | None,
) -> tuple[ProviderModelUsage, ...]:
    if calls == 0:
        return usage
    rows = list(usage)
    for index, row in enumerate(rows):
        if (row.vendor, row.model) == (provider.vendor, provider.model):
            rows[index] = ProviderModelUsage(
                vendor=row.vendor,
                model=row.model,
                calls=row.calls + calls,
                input_tokens=_add_known(row.input_tokens, input_tokens),
                output_tokens=_add_known(row.output_tokens, output_tokens),
            )
            break
    else:
        rows.append(
            ProviderModelUsage(
                vendor=provider.vendor,
                model=provider.model,
                calls=calls,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        )
    return tuple(rows)


def _add_known(left: int | None, right: int | None) -> int | None:
    return left + right if left is not None and right is not None else None


def _usage_from_error(error: ProviderError) -> tuple[int, int | None, int | None]:
    calls = error.details.get("provider_calls_attempted")
    if type(calls) is not int or calls < 0:
        calls = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    rows = error.details.get("settled_model_usage")
    if type(rows) is tuple:
        for row in rows:
            if not isinstance(row, Mapping) or row.get("unit") != "tokens":
                continue
            candidate_input = row.get("input_count")
            candidate_output = row.get("output_count")
            input_tokens = candidate_input if type(candidate_input) is int else None
            output_tokens = candidate_output if type(candidate_output) is int else None
            break
    return calls, input_tokens, output_tokens


def _cleanup_failed(error: OCRLLMError) -> bool:
    return bool(
        error.details.get("provider_client_cleanup_failed") is True
        or error.details.get("provider_client_closed") is False
    )


def _bounded_error_description(error: ProviderError) -> str:
    description = str(error).strip()
    if len(description) <= _MAX_PROVIDER_FAILURE_DESCRIPTION_CHARS:
        return description
    return description[: _MAX_PROVIDER_FAILURE_DESCRIPTION_CHARS - 3] + "..."
