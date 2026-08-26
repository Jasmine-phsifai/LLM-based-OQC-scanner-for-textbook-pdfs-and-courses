"""Settle one whole long-MP3 request into temporary recovery state."""

from __future__ import annotations

from collections.abc import Callable

from ..audio.attach_long_audio_slots_evidence_to_error import (
    attach_long_audio_slots_evidence_to_error,
)
from ..audio.build_long_audio_no_speech_slot import build_long_audio_no_speech_slot
from ..audio.build_long_audio_settled_slot import build_long_audio_settled_slot
from ..audio.fingerprint_long_audio_request import (
    LONG_AUDIO_REQUEST_IDENTITY_VERSION,
    fingerprint_long_audio_request,
)
from ..audio.long_audio_partial_state import (
    LONG_AUDIO_PARTIAL_STATE_VERSION,
    LongAudioPartialState,
)
from ..audio.long_audio_settled_slot import LongAudioSettledSlot
from ..audio.reuse_long_audio_partial_state import reuse_long_audio_partial_state
from ..audio.transcription_prompt import (
    AUDIO_TRANSCRIPTION_PROMPT,
    NO_SPEECH_SENTINEL,
)
from ..config import Config
from ..errors import NoSpeechDetected, OCRLLMError
from ..processor_output import ProcessorOutput
from ..providers.google_genai.recognize_uploaded_mp3 import recognize_uploaded_mp3
from .build_long_mp3_processor_output import build_long_mp3_processor_output


def recognize_long_mp3_whole(
    snapshot,
    *,
    config: Config,
    persist_state: Callable[[LongAudioPartialState], None],
    saved_state,
) -> tuple[ProcessorOutput, int]:
    """Reuse or settle one whole-file slot and persist it before returning."""
    model = config.audio_model.name
    assert type(model) is str
    request_fingerprint = fingerprint_long_audio_request(
        source_sha256=snapshot.sha256,
        mode="whole",
        provider="google",
        model=model,
        transport="google_files",
    )
    request_plan = (request_fingerprint,)
    slots: tuple[LongAudioSettledSlot, ...] = ()
    if saved_state is not None:
        slots = reuse_long_audio_partial_state(saved_state, request_plan)
    if slots:
        if slots[0].markdown == NO_SPEECH_SENTINEL:
            raise NoSpeechDetected(
                details={
                    "provider": slots[0].provider,
                    "model": slots[0].model,
                    "provider_calls_attempted": 0,
                    "remote_file_deleted": (
                        slots[0].provider_file_cleanup_succeeded
                    ),
                    "provider_client_closed": (
                        slots[0].provider_client_cleanup_succeeded
                    ),
                }
            ) from None
        return _build_reused_output(snapshot, slots[0]), 0

    no_speech_error = None
    try:
        response = recognize_uploaded_mp3(
            snapshot,
            prompt=AUDIO_TRANSCRIPTION_PROMPT,
            config=config,
        )
    except NoSpeechDetected as error:
        no_speech_error = error
        response = None
    try:
        if no_speech_error is None:
            output = _with_current_run_count(
                build_long_mp3_processor_output(snapshot, response, config=config),
                count=1,
            )
            slot = build_long_audio_settled_slot(
                output,
                window_index=0,
                request_fingerprint=request_fingerprint,
            )
        else:
            slot = build_long_audio_no_speech_slot(
                window_index=0,
                request_fingerprint=request_fingerprint,
                model=model,
                error=no_speech_error,
            )
        try:
            persist_state(
                LongAudioPartialState(
                    state_version=LONG_AUDIO_PARTIAL_STATE_VERSION,
                    identity_version=LONG_AUDIO_REQUEST_IDENTITY_VERSION,
                    mode="whole",
                    interval_minutes=None,
                    request_fingerprints=request_plan,
                    slots=(slot,),
                ),
            )
        except OCRLLMError as error:
            attach_long_audio_slots_evidence_to_error(error, (slot,))
            raise
    except OCRLLMError as error:
        if "provider_calls_attempted" not in error.details:
            error._add_safe_detail("provider_calls_attempted", 1)
        raise
    if no_speech_error is not None:
        raise no_speech_error
    return output, 1


def _build_reused_output(snapshot, slot: LongAudioSettledSlot) -> ProcessorOutput:
    return ProcessorOutput(
        media_type="audio",
        markdown=slot.markdown,
        status=slot.status,
        warnings=slot.warnings,
        metadata={
            "provider": slot.provider,
            "model": slot.model,
            "transport": slot.transport,
            "provider_call_count": slot.provider_calls_attempted,
            "current_run_provider_call_count": 0,
            "current_model_token_usage": (),
            "historical_model_token_usage": (
                {
                    "model": slot.model,
                    "input_tokens": slot.input_tokens,
                    "output_tokens": slot.output_tokens,
                },
            ),
            "duration_seconds": snapshot.duration_seconds,
            "byte_size": snapshot.byte_size,
            "remote_file_deleted": slot.provider_file_cleanup_succeeded,
            "provider_client_closed": slot.provider_client_cleanup_succeeded,
        },
    )


def _with_current_run_count(output: ProcessorOutput, *, count: int) -> ProcessorOutput:
    metadata = dict(output.metadata)
    metadata["current_run_provider_call_count"] = count
    return ProcessorOutput(
        media_type=output.media_type,
        markdown=output.markdown,
        status=output.status,
        warnings=output.warnings,
        metadata=metadata,
    )
