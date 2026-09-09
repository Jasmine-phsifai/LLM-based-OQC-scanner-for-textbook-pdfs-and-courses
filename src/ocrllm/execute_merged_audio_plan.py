"""Execute audio slices through fixed provider lanes."""

from __future__ import annotations

import hashlib
import json

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from threading import Event, Lock

from .audio_gap_summary import is_output_limit_failure
from .audio.build_long_audio_interval_prompt import build_long_audio_interval_prompt
from .audio.build_long_audio_interval_upload_snapshot import (
    build_long_audio_interval_upload_snapshot,
)
from .audio.build_long_audio_interval_windows import LongAudioIntervalWindow
from .audio.materialize_long_audio_interval import materialize_long_audio_interval
from .audio.snapshot_long_mp3 import LongMP3Snapshot
from .audio.transcription_prompt import AUDIO_TRANSCRIPTION_PROMPT
from .errors import NoSpeechDetected, OCRLLMError, OutputError, ProviderError
from .merged_audio_resume_state import MergedAudioResumeState, MergedAudioSlot
from .output.save_merged_audio_resume_state_atomically import (
    save_merged_audio_resume_state_atomically,
)
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
from .providers.call_provider_model_with_retries import (
    call_provider_model_with_retries,
)
from .providers.provider_model import ProviderModel
from .providers.recognize_provider_model_audio import recognize_provider_model_audio


def execute_merged_audio_plan(
    state: MergedAudioResumeState,
    snapshot: LongMP3Snapshot,
    *,
    provider_lanes: tuple[tuple[ProviderModel, ...], ...],
    state_path: Path,
    timeout_seconds: float,
    failed_slice_minutes: int | None = None,
) -> tuple[
    MergedAudioResumeState,
    tuple[ProviderModelUsage, ...],
    int,
    tuple[dict[str, int | str], ...],
]:
    """Settle fixed audio lane assignments with one serialized state owner."""
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
    owner = _MergedAudioStateOwner(
        state,
        state_path=state_path,
        provider_lanes=provider_lanes,
    )
    lane_failures: list[dict[str, int | str]] = []
    if len(active_lanes) == 1:
        lane_failures.extend(
            _execute_merged_audio_lane(
                state,
                snapshot,
                lane_index=active_lanes[0],
                provider_lanes=provider_lanes,
                timeout_seconds=timeout_seconds,
                owner=owner,
                stop=stop,
                failed_slice_minutes=failed_slice_minutes,
            )
        )
    else:
        primary_error: BaseException | None = None
        with ThreadPoolExecutor(
            max_workers=len(active_lanes),
            thread_name_prefix="ocrllm-audio-lane",
        ) as executor:
            futures = tuple(
                executor.submit(
                    _execute_merged_audio_lane,
                    state,
                    snapshot,
                    lane_index=lane_index,
                    provider_lanes=provider_lanes,
                    timeout_seconds=timeout_seconds,
                    owner=owner,
                    stop=stop,
                    failed_slice_minutes=failed_slice_minutes,
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


class _MergedAudioStateOwner:
    """Serialize sparse audio state and usage merges across active lanes."""

    def __init__(
        self,
        state: MergedAudioResumeState,
        *,
        state_path: Path,
        provider_lanes: tuple[tuple[ProviderModel, ...], ...],
    ) -> None:
        self._lock = Lock()
        self._state = state
        self.gap_policy = state.audio_gap_policy
        self._state_path = state_path
        self._current_usage: tuple[ProviderModelUsage, ...] = ()
        self._usage_order = build_provider_model_usage_order(
            provider_lanes,
            slot_count=len(state.slots),
        )

    def checkpoint(
        self,
        outcome: MergedAudioSlot,
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
    ) -> tuple[MergedAudioResumeState, tuple[ProviderModelUsage, ...]]:
        with self._lock:
            return self._state, self._current_usage

    def plan_failed_subslots(self, index, *, interval_minutes):
        from .resplit_failed_audio_slots import resplit_failed_audio_slots
        with self._lock:
            updated = resplit_failed_audio_slots(
                self._state, interval_minutes=interval_minutes,
                slot_indices=(index,), only_output_limit=True,
            )
            if updated is self._state:
                return None
            save_merged_audio_resume_state_atomically(self._state_path, updated)
            self._state = updated
            return updated.slots[index]

    def current_call_count(self) -> int:
        with self._lock:
            return sum(row.calls for row in self._current_usage)


def _execute_merged_audio_lane(
    initial_state: MergedAudioResumeState,
    snapshot: LongMP3Snapshot,
    *,
    lane_index: int,
    provider_lanes: tuple[tuple[ProviderModel, ...], ...],
    timeout_seconds: float,
    owner: _MergedAudioStateOwner,
    stop: Event,
    failed_slice_minutes: int | None = None,
) -> tuple[dict[str, int | str], ...]:
    """Run one fixed audio lane serially with one active clip at a time."""
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
            if slot.subslots:
                slot_failures, success_index = _execute_audio_subslots(
                    slot, snapshot, provider_lane=provider_lane, start_index=last_success_index,
                    timeout_seconds=timeout_seconds, owner=owner, stop=stop,
                )
            elif initial_state.mode == "whole" and snapshot.path.suffix.casefold() == ".mp3":
                slot_failures, success_index = _execute_audio_slot(
                    slot,
                    snapshot,
                    provider_lane=provider_lane,
                    start_index=last_success_index,
                    prompt=AUDIO_TRANSCRIPTION_PROMPT,
                    request_kind="whole",
                    timeout_seconds=timeout_seconds,
                    owner=owner,
                    stop=stop,
                )
            else:
                window = _window_from_slot(slot)
                with materialize_long_audio_interval(
                    snapshot.path,
                    window=window,
                ) as segment:
                    upload = build_long_audio_interval_upload_snapshot(
                        segment,
                        duration_seconds=(
                            slot.actual_end_seconds - slot.actual_start_seconds
                        ),
                    )
                    slot_failures, success_index = _execute_audio_slot(
                        slot,
                        upload,
                        provider_lane=provider_lane,
                        start_index=last_success_index,
                        prompt=(AUDIO_TRANSCRIPTION_PROMPT if initial_state.mode == "whole"
                                else build_long_audio_interval_prompt(window)),
                        request_kind=initial_state.mode,
                        timeout_seconds=timeout_seconds,
                        owner=owner,
                        stop=stop,
                    )
            if success_index is None and failed_slice_minutes is not None and not stop.is_set():
                divided = owner.plan_failed_subslots(slot.index, interval_minutes=failed_slice_minutes)
                if divided is not None:
                    slot_failures, success_index = _execute_audio_subslots(
                        divided, snapshot, provider_lane=provider_lane, start_index=last_success_index,
                        timeout_seconds=timeout_seconds, owner=owner, stop=stop,
                    )
                    slot_failures = ({
                        "slot_index": divided.index, "vendor": divided.vendor,
                        "model": divided.model, "code": divided.error_code,
                        "description": divided.error_description,
                    }, *slot_failures)
            if stop.is_set():
                break
            if success_index is not None:
                provider_failures.extend(slot_failures)
                last_success_index = success_index
        return tuple(provider_failures)
    except BaseException:
        stop.set()
        raise


def _execute_audio_slot(
    slot: MergedAudioSlot, request_snapshot: LongMP3Snapshot, *, provider_lane,
    start_index, prompt, request_kind, timeout_seconds, owner, stop,
):
    """Persist every short-leaf output-cap attempt; never accept other errors."""
    slot_failures = []
    for offset in range(len(provider_lane)):
        if stop.is_set():
            break
        provider_index = (start_index + offset) % len(provider_lane)
        provider = provider_lane[provider_index]
        current = slot
        bounded_cap = (owner.gap_policy is not None
                       and slot.logical_end_seconds-slot.logical_start_seconds <= 120)
        identity = _output_limit_identity(provider, prompt) if bounded_cap else None
        if bounded_cap and current.output_limit_identity == identity and current.output_limit_attempts >= 3:
            continue
        while not stop.is_set():
            try:
                call_result = call_provider_model_with_retries(
                    provider, lambda: recognize_provider_model_audio(
                        provider, request_snapshot, prompt=prompt, request_kind=request_kind,
                        timeout_seconds=timeout_seconds,
                    ),
                )
                response = call_result.response
            except NoSpeechDetected as error:
                calls, input_tokens, output_tokens = provider_failure_usage(error)
                outcome = _settled_slot(current, provider=provider, no_speech=True)
                owner.checkpoint(outcome, provider=provider, calls=calls,
                    input_tokens=input_tokens, output_tokens=output_tokens,
                    cleanup_failed=provider_cleanup_failed(error))
                return tuple(slot_failures), provider_index
            except ProviderError as error:
                calls, input_tokens, output_tokens = provider_failure_usage(error)
                outcome = _failed_slot(current, provider=provider, error=error)
                if bounded_cap and is_output_limit_failure(outcome):
                    previous = current.output_limit_attempts if current.output_limit_identity == identity else 0
                    outcome = replace(outcome, output_limit_attempts=min(3, previous+1),
                                      output_limit_identity=identity)
                owner.checkpoint(outcome, provider=provider, calls=calls,
                    input_tokens=input_tokens, output_tokens=output_tokens,
                    cleanup_failed=provider_cleanup_failed(error))
                slot_failures.append({'slot_index':slot.index, 'vendor':provider.vendor,
                    'model':provider.model, 'code':error.code, 'description':outcome.error_description})
                if bounded_cap and is_output_limit_failure(outcome) and outcome.output_limit_attempts < 3:
                    current = outcome
                    continue
                break
            outcome = _settled_slot(current, provider=provider, markdown=response.markdown)
            owner.checkpoint(outcome, provider=provider, calls=call_result.calls,
                input_tokens=_add_known(call_result.failed_input_tokens,response.input_tokens),
                output_tokens=_add_known(call_result.failed_output_tokens,response.output_tokens),
                cleanup_failed=call_result.prior_cleanup_failed or response.provider_cleanup_failed)
            return tuple(slot_failures), provider_index
    return tuple(slot_failures), None


def _output_limit_identity(provider, prompt):
    # Opaque request identity; no secret, backend constraint, or service state is copied.
    settings = provider.settings
    value = (provider.vendor, provider.model, provider.adapter_id, prompt,
             getattr(settings, 'base_url', None), getattr(settings, 'send_audio_prompt', None),
             getattr(settings, 'audio_response_validation', None))
    return hashlib.sha256(json.dumps(value, ensure_ascii=False).encode()).hexdigest()


def _window_from_slot(slot: MergedAudioSlot) -> LongAudioIntervalWindow:
    return LongAudioIntervalWindow(
        index=slot.index,
        logical_start_seconds=slot.logical_start_seconds,
        logical_end_seconds=slot.logical_end_seconds,
        actual_start_seconds=slot.actual_start_seconds,
        actual_end_seconds=slot.actual_end_seconds,
    )


def _settled_slot(
    slot: MergedAudioSlot,
    *,
    provider: ProviderModel,
    markdown: str | None = None,
    no_speech: bool = False,
) -> MergedAudioSlot:
    return MergedAudioSlot(
        index=slot.index,
        logical_start_seconds=slot.logical_start_seconds,
        logical_end_seconds=slot.logical_end_seconds,
        actual_start_seconds=slot.actual_start_seconds,
        actual_end_seconds=slot.actual_end_seconds,
        status="settled",
        no_speech=no_speech,
        output_limit_attempts=slot.output_limit_attempts,
        output_limit_identity=slot.output_limit_identity,
        markdown=markdown,
        markdown_sha256=(
            None
            if markdown is None
            else hashlib.sha256(markdown.encode("utf-8")).hexdigest()
        ),
        vendor=provider.vendor,
        model=provider.model,
    )


def _failed_slot(
    slot: MergedAudioSlot,
    *,
    provider: ProviderModel,
    error: ProviderError,
) -> MergedAudioSlot:
    return MergedAudioSlot(
        index=slot.index,
        logical_start_seconds=slot.logical_start_seconds,
        logical_end_seconds=slot.logical_end_seconds,
        actual_start_seconds=slot.actual_start_seconds,
        actual_end_seconds=slot.actual_end_seconds,
        status="failed",
        vendor=provider.vendor,
        model=provider.model,
        error_code=error.code,
        error_description=bounded_provider_failure_description(error),
    )


def _checkpoint_outcome(
    state: MergedAudioResumeState,
    outcome: MergedAudioSlot,
    *,
    provider: ProviderModel,
    calls: int,
    input_tokens: int | None,
    output_tokens: int | None,
    cleanup_failed: bool,
    state_path: Path,
    current_usage: tuple[ProviderModelUsage, ...],
    usage_order: dict[tuple[str, str], int],
) -> tuple[MergedAudioResumeState, tuple[ProviderModelUsage, ...]]:
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
        save_merged_audio_resume_state_atomically(state_path, updated)
    except OutputError as error:
        error._add_safe_detail(
            "provider_calls_attempted",
            sum(row.calls for row in current_usage),
        )
        raise
    return updated, current_usage


def _add_known(left: int | None, right: int | None) -> int | None:
    return left + right if left is not None and right is not None else None


class _MergedAudioSubslotOwner:
    """Checkpoint each child through the same parent state and usage owner."""

    def __init__(self, parent, owner):
        self.parent = parent
        self.owner = owner
        self.gap_policy = owner.gap_policy

    def checkpoint(self, outcome, **usage):
        children = list(self.parent.subslots)
        children[outcome.index] = outcome
        self.parent = replace(self.parent, subslots=tuple(children))
        if all(child.status == 'settled' for child in children):
            markdown = '\n\n'.join(child.markdown.strip() for child in children if child.markdown)
            self.parent = replace(
                _settled_slot(self.parent, provider=usage['provider'],
                              markdown=markdown or None, no_speech=not markdown),
                subslots=tuple(children),
            )
        elif outcome.status == 'failed':
            self.parent = replace(self.parent, error_code=outcome.error_code,
                                  error_description=outcome.error_description)
        self.owner.checkpoint(self.parent, **usage)


def _execute_audio_subslots(parent, snapshot, *, provider_lane, start_index,
                            timeout_seconds, owner, stop):
    child_owner = _MergedAudioSubslotOwner(parent, owner)
    failures = []
    success_index = start_index
    for child in parent.subslots:
        if child.status == 'settled':
            continue
        if stop.is_set():
            break
        window = _window_from_slot(child)
        with materialize_long_audio_interval(snapshot.path, window=window) as segment:
            upload = build_long_audio_interval_upload_snapshot(
                segment, duration_seconds=child.actual_end_seconds-child.actual_start_seconds,
            )
            child_failures, succeeded = _execute_audio_slot(
                child, upload, provider_lane=provider_lane, start_index=success_index,
                prompt=build_long_audio_interval_prompt(window), request_kind='interval',
                timeout_seconds=timeout_seconds, owner=child_owner, stop=stop,
            )
        for failure in child_failures:
            failures.append({**failure, 'slot_index': parent.index, 'subslot_index': child.index})
        if succeeded is not None:
            success_index = succeeded
    return tuple(failures), success_index
