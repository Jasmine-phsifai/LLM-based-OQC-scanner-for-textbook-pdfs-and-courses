"""Execute merged-image slots through fixed provider lanes."""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from threading import Event, Lock

from .config import Config
from .errors import OCRLLMError, OutputError, ProviderError, ResumeStateError
from .fingerprint_image_sources import fingerprint_image_sources
from .imaging.snapshot_image_group import snapshot_image_group
from .merged_image_resume_state import MergedImageResumeState, MergedImageSlot
from .output.save_merged_image_resume_state_atomically import (
    save_merged_image_resume_state_atomically,
)
from .providers.provider_model import ProviderModel
from .provider_model_usage import (
    ProviderModelUsage,
    add_provider_model_usage,
    build_provider_model_usage_order,
)
from .provider_failure_evidence import (
    bounded_provider_failure_description,
    provider_cleanup_failed,
    provider_failure_usage,
)
from .providers.recognize_provider_model_images import (
    recognize_provider_model_images,
)
from .providers.vision_provider_response import VisionProviderResponse


def execute_merged_image_plan(
    state: MergedImageResumeState,
    batches: tuple[tuple[Path, ...], ...],
    *,
    provider_lanes: tuple[tuple[ProviderModel, ...], ...],
    prompt: str,
    state_path: Path,
    timeout_seconds: float,
) -> tuple[
    MergedImageResumeState,
    tuple[ProviderModelUsage, ...],
    int,
    tuple[dict[str, int | str], ...],
]:
    """Settle fixed lane assignments with one serialized state owner."""
    reused_slot_count = sum(slot.status == "settled" for slot in state.slots)
    active_lanes = tuple(
        lane_index
        for lane_index in range(min(len(provider_lanes), len(state.slots)))
        if any(
            state.slots[slot_index].status != "settled"
            for slot_index in range(
                lane_index,
                len(state.slots),
                len(provider_lanes),
            )
        )
    )
    if not active_lanes:
        return state, (), reused_slot_count, ()

    stop = Event()
    owner = _MergedImageStateOwner(
        state,
        state_path=state_path,
        provider_lanes=provider_lanes,
    )
    lane_failures: list[dict[str, int | str]] = []
    if len(active_lanes) == 1:
        lane_failures.extend(
            _execute_merged_image_lane(
                state,
                batches,
                lane_index=active_lanes[0],
                provider_lanes=provider_lanes,
                prompt=prompt,
                timeout_seconds=timeout_seconds,
                owner=owner,
                stop=stop,
            )
        )
    else:
        primary_error: BaseException | None = None
        with ThreadPoolExecutor(
            max_workers=len(active_lanes),
            thread_name_prefix="ocrllm-image-lane",
        ) as executor:
            futures = tuple(
                executor.submit(
                    _execute_merged_image_lane,
                    state,
                    batches,
                    lane_index=lane_index,
                    provider_lanes=provider_lanes,
                    prompt=prompt,
                    timeout_seconds=timeout_seconds,
                    owner=owner,
                    stop=stop,
                )
                for lane_index in active_lanes
            )
            for future in as_completed(futures):
                try:
                    lane_failures.extend(future.result())
                except BaseException as error:
                    stop.set()
                    if primary_error is None:
                        primary_error = error
        if primary_error is not None:
            if isinstance(primary_error, OCRLLMError):
                primary_error._add_safe_detail(
                    "provider_calls_attempted",
                    owner.current_call_count(),
                )
            raise primary_error

    settled_state, current_usage = owner.result()
    provider_failures = tuple(
        sorted(lane_failures, key=lambda row: row["slot_index"])
    )
    return settled_state, current_usage, reused_slot_count, provider_failures


class _MergedImageStateOwner:
    """Serialize sparse state and usage merges from concurrent image lanes."""

    def __init__(
        self,
        state: MergedImageResumeState,
        *,
        state_path: Path,
        provider_lanes: tuple[tuple[ProviderModel, ...], ...],
    ) -> None:
        self._lock = Lock()
        self._state = state
        self._state_path = state_path
        self._current_usage: tuple[ProviderModelUsage, ...] = ()
        self._usage_order = build_provider_model_usage_order(
            provider_lanes,
            slot_count=len(state.slots),
        )

    def checkpoint(
        self,
        outcome: MergedImageSlot,
        *,
        provider: ProviderModel,
        calls: int,
        input_tokens: int | None,
        output_tokens: int | None,
        cleanup_failed: bool,
    ) -> None:
        with self._lock:
            self._state, self._current_usage = _checkpoint_outcome(
                self._state,
                outcome,
                provider=provider,
                calls=calls,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cleanup_failed=cleanup_failed,
                state_path=self._state_path,
                current_usage=self._current_usage,
                usage_order=self._usage_order,
            )

    def result(
        self,
    ) -> tuple[MergedImageResumeState, tuple[ProviderModelUsage, ...]]:
        with self._lock:
            return self._state, self._current_usage

    def current_call_count(self) -> int:
        with self._lock:
            return sum(row.calls for row in self._current_usage)


def _execute_merged_image_lane(
    initial_state: MergedImageResumeState,
    batches: tuple[tuple[Path, ...], ...],
    *,
    lane_index: int,
    provider_lanes: tuple[tuple[ProviderModel, ...], ...],
    prompt: str,
    timeout_seconds: float,
    owner: _MergedImageStateOwner,
    stop: Event,
) -> tuple[dict[str, int | str], ...]:
    """Run one fixed lane serially while other lanes progress independently."""
    provider_lane = provider_lanes[lane_index]
    lane_count = len(provider_lanes)
    last_success_index = 0
    provider_failures: list[dict[str, int | str]] = []
    try:
        for slot_index in range(lane_index, len(initial_state.slots), lane_count):
            slot = initial_state.slots[slot_index]
            if slot.status == "settled":
                continue
            if stop.is_set():
                break
            batch = batches[slot_index]
            with snapshot_image_group(batch, config=Config()) as snapshots:
                actual_sources = fingerprint_image_sources(batch, snapshots)
                expected_sources = tuple(
                    initial_state.sources[index] for index in slot.source_indexes
                )
                if actual_sources != expected_sources:
                    raise ResumeStateError(
                        "An image source changed after the merged plan was validated.",
                        code="RESUME_STATE_MISMATCH",
                        details={"provider_calls_attempted": 0},
                    ) from None
                slot_failures: list[dict[str, int | str]] = []
                for offset in range(len(provider_lane)):
                    if stop.is_set():
                        break
                    provider_index = (
                        last_success_index + offset
                    ) % len(provider_lane)
                    provider = provider_lane[provider_index]
                    try:
                        response = recognize_provider_model_images(
                            provider,
                            snapshots,
                            prompt=prompt,
                            timeout_seconds=timeout_seconds,
                        )
                    except ProviderError as error:
                        calls, input_tokens, output_tokens = provider_failure_usage(error)
                        description = bounded_provider_failure_description(error)
                        failed_slot = MergedImageSlot(
                            index=slot.index,
                            source_indexes=slot.source_indexes,
                            status="failed",
                            vendor=provider.vendor,
                            model=provider.model,
                            error_code=error.code,
                            error_description=description,
                        )
                        owner.checkpoint(
                            failed_slot,
                            provider=provider,
                            calls=calls,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            cleanup_failed=provider_cleanup_failed(error),
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
                    owner.checkpoint(
                        settled_slot,
                        provider=provider,
                        calls=1,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cleanup_failed=cleanup_failed,
                    )
                    provider_failures.extend(slot_failures)
                    last_success_index = provider_index
                    break
        return tuple(provider_failures)
    except BaseException:
        stop.set()
        raise


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
    usage_order: dict[tuple[str, str], int],
) -> tuple[MergedImageResumeState, tuple[ProviderModelUsage, ...]]:
    slots = list(state.slots)
    slots[outcome.index] = outcome
    usage = add_provider_model_usage(
        state.usage,
        provider=provider,
        calls=calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        usage_order=usage_order,
    )
    current_usage = add_provider_model_usage(
        current_usage,
        provider=provider,
        calls=calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        usage_order=usage_order,
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
