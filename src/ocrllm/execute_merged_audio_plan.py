"""Execute unresolved audio slices through one serial provider lane."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Literal

from .audio.build_long_audio_interval_prompt import build_long_audio_interval_prompt
from .audio.build_long_audio_interval_upload_snapshot import (
    build_long_audio_interval_upload_snapshot,
)
from .audio.build_long_audio_interval_windows import LongAudioIntervalWindow
from .audio.materialize_long_audio_interval import materialize_long_audio_interval
from .audio.probe_short_mp3 import MAX_SHORT_MP3_DURATION_SECONDS
from .audio.snapshot_long_mp3 import LongMP3Snapshot
from .audio.transcription_prompt import AUDIO_TRANSCRIPTION_PROMPT
from .errors import NoSpeechDetected, OutputError, ProviderError
from .merged_audio_resume_state import MergedAudioResumeState, MergedAudioSlot
from .output.save_merged_audio_resume_state_atomically import (
    save_merged_audio_resume_state_atomically,
)
from .provider_model_usage import ProviderModelUsage
from .providers.provider_model import ProviderModel
from .providers.recognize_provider_model_audio import recognize_provider_model_audio


_MAX_PROVIDER_FAILURE_DESCRIPTION_CHARS = 512


def execute_merged_audio_plan(
    state: MergedAudioResumeState,
    snapshot: LongMP3Snapshot,
    *,
    provider_lane: tuple[ProviderModel, ...],
    state_path: Path,
    timeout_seconds: float,
) -> tuple[
    MergedAudioResumeState,
    tuple[ProviderModelUsage, ...],
    int,
    tuple[dict[str, int | str], ...],
]:
    """Settle unresolved audio slots through one serial fallback lane."""
    current_usage: tuple[ProviderModelUsage, ...] = ()
    reused_slot_count = 0
    provider_failures: list[dict[str, int | str]] = []
    last_success_index = 0
    for slot in state.slots:
        if slot.status == "settled":
            reused_slot_count += 1
            continue
        if state.mode == "whole":
            transport = (
                "inline"
                if snapshot.duration_seconds <= MAX_SHORT_MP3_DURATION_SECONDS
                else "files"
            )
            (
                state,
                current_usage,
                slot_failures,
                success_index,
            ) = _execute_audio_slot(
                state,
                slot,
                snapshot,
                provider_lane=provider_lane,
                start_index=last_success_index,
                prompt=AUDIO_TRANSCRIPTION_PROMPT,
                transport=transport,
                state_path=state_path,
                timeout_seconds=timeout_seconds,
                current_usage=current_usage,
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
                (
                    state,
                    current_usage,
                    slot_failures,
                    success_index,
                ) = _execute_audio_slot(
                    state,
                    slot,
                    upload,
                    provider_lane=provider_lane,
                    start_index=last_success_index,
                    prompt=build_long_audio_interval_prompt(window),
                    transport="files",
                    state_path=state_path,
                    timeout_seconds=timeout_seconds,
                    current_usage=current_usage,
                )
        if success_index is not None:
            provider_failures.extend(slot_failures)
            last_success_index = success_index
    return (
        state,
        current_usage,
        reused_slot_count,
        tuple(provider_failures),
    )


def _execute_audio_slot(
    state: MergedAudioResumeState,
    slot: MergedAudioSlot,
    request_snapshot: LongMP3Snapshot,
    *,
    provider_lane: tuple[ProviderModel, ...],
    start_index: int,
    prompt: str,
    transport: Literal["inline", "files"],
    state_path: Path,
    timeout_seconds: float,
    current_usage: tuple[ProviderModelUsage, ...],
) -> tuple[
    MergedAudioResumeState,
    tuple[ProviderModelUsage, ...],
    tuple[dict[str, int | str], ...],
    int | None,
]:
    """Attempt one prepared audio slot through each candidate at most once."""
    slot_failures: list[dict[str, int | str]] = []
    for offset in range(len(provider_lane)):
        provider_index = (start_index + offset) % len(provider_lane)
        provider = provider_lane[provider_index]
        try:
            response = recognize_provider_model_audio(
                provider,
                request_snapshot,
                prompt=prompt,
                transport=transport,
                timeout_seconds=timeout_seconds,
            )
        except NoSpeechDetected as error:
            calls, input_tokens, output_tokens = _usage_from_error(error)
            outcome = _settled_slot(slot, provider=provider, no_speech=True)
            state, current_usage = _checkpoint_outcome(
                state,
                outcome,
                provider=provider,
                calls=calls,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cleanup_failed=_cleanup_failed(error),
                state_path=state_path,
                current_usage=current_usage,
            )
            return state, current_usage, tuple(slot_failures), provider_index
        except ProviderError as error:
            calls, input_tokens, output_tokens = _usage_from_error(error)
            outcome = _failed_slot(slot, provider=provider, error=error)
            assert outcome.error_description is not None
            description = outcome.error_description
            state, current_usage = _checkpoint_outcome(
                state,
                outcome,
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

        cleanup_failed = not response.client_closed or (
            transport == "files" and not response.remote_file_deleted
        )
        outcome = _settled_slot(
            slot,
            provider=provider,
            markdown=response.markdown,
        )
        state, current_usage = _checkpoint_outcome(
            state,
            outcome,
            provider=provider,
            calls=1,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cleanup_failed=cleanup_failed,
            state_path=state_path,
            current_usage=current_usage,
        )
        return state, current_usage, tuple(slot_failures), provider_index
    return state, current_usage, (), None


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
        error_description=_bounded_error_description(error),
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
) -> tuple[MergedAudioResumeState, tuple[ProviderModelUsage, ...]]:
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
        save_merged_audio_resume_state_atomically(state_path, updated)
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


def _usage_from_error(error: ProviderError | NoSpeechDetected) -> tuple[
    int,
    int | None,
    int | None,
]:
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


def _cleanup_failed(error: ProviderError | NoSpeechDetected) -> bool:
    return bool(
        error.details.get("provider_file_cleanup_failed") is True
        or error.details.get("remote_file_deleted") is False
        or error.details.get("provider_client_cleanup_failed") is True
        or error.details.get("provider_client_closed") is False
    )


def _bounded_error_description(error: ProviderError) -> str:
    description = str(error).strip()
    if len(description) <= _MAX_PROVIDER_FAILURE_DESCRIPTION_CHARS:
        return description
    return description[: _MAX_PROVIDER_FAILURE_DESCRIPTION_CHARS - 3] + "..."
