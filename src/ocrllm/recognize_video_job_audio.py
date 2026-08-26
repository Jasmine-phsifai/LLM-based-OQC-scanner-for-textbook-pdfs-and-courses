"""Recognize or reuse the audio unit of one video job."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .audio.snapshot_long_mp3 import LongMP3Snapshot
from .audio.snapshot_short_mp3 import ShortMP3Snapshot
from .audio.snapshot_video_mp3 import snapshot_video_mp3
from .audio.transcription_prompt import AUDIO_TRANSCRIPTION_PROMPT
from .build_recognition_result import build_recognition_result
from .config import Config
from .errors import NoSpeechDetected, OCRLLMError, ResumeStateError
from .fingerprint_video_short_audio_request import (
    fingerprint_video_short_audio_request,
)
from .processor_output import ProcessorOutput
from .processors.build_short_mp3_processor_output import (
    build_short_mp3_processor_output,
)
from .processors.recognize_long_mp3_intervals import recognize_long_mp3_intervals
from .processors.recognize_long_mp3_whole import recognize_long_mp3_whole
from .providers.google_genai.recognize_short_mp3 import recognize_short_mp3
from .providers.provider_request_start_gate import (
    reuse_or_create_provider_request_start_gate,
)
from .raise_if_cancelled import raise_if_cancelled
from .result import RecognitionResult
from .source_fingerprint_path import source_fingerprint_path
from .video_job_journal import VideoJobJournal
from .video_job_state import VideoAudioState, VideoShortAudioState


def recognize_video_job_audio(
    audio: VideoAudioState,
    *,
    config: Config,
    journal: VideoJobJournal,
) -> tuple[RecognitionResult | None, OCRLLMError | None]:
    """Return one settled result/error while persisting every paid slot."""
    if audio.state == "absent":
        return None, None
    if audio.state != "ready" or audio.artifact is None or audio.mode is None:
        raise ResumeStateError(
            "The video audio unit is not ready for recognition.",
            code="RESUME_STATE_INVALID",
        ) from None
    try:
        raise_if_cancelled(config.cancellation)
        artifact = source_fingerprint_path(audio.artifact)
        snapshot_context = (
            snapshot_video_mp3(
                artifact,
                temp_dir=config.temp_dir,
                interval_mode=True,
            )
            if audio.mode == "interval"
            else snapshot_video_mp3(artifact, temp_dir=config.temp_dir)
        )
        with snapshot_context as snapshot:
            _validate_snapshot(audio, snapshot)
            with reuse_or_create_provider_request_start_gate(
                config.execution.provider_request_start_interval_seconds
            ):
                output = _recognize_snapshot(
                    snapshot,
                    audio=audio,
                    config=config,
                    journal=journal,
                )
        return build_recognition_result(output, output_path=None), None
    except NoSpeechDetected as error:
        return None, error
    except OCRLLMError as error:
        return None, error


def _recognize_snapshot(
    snapshot,
    *,
    audio: VideoAudioState,
    config: Config,
    journal: VideoJobJournal,
) -> ProcessorOutput:
    if audio.mode == "short":
        return _recognize_short(snapshot, audio=audio, config=config, journal=journal)
    long_snapshot = LongMP3Snapshot(
        path=snapshot.path,
        byte_size=snapshot.byte_size,
        sha256=snapshot.sha256,
        duration_seconds=snapshot.duration_seconds,
    )
    if audio.mode == "whole":
        output, _ = recognize_long_mp3_whole(
            long_snapshot,
            config=config,
            persist_state=journal.persist_long_audio_state,
            saved_state=audio.long_state,
        )
        return output
    assert audio.interval_minutes is not None
    output, _ = recognize_long_mp3_intervals(
        long_snapshot,
        config=config,
        interval_minutes=audio.interval_minutes,
        persist_state=journal.persist_long_audio_state,
        saved_state=audio.long_state,
    )
    return output


def _recognize_short(
    snapshot,
    *,
    audio: VideoAudioState,
    config: Config,
    journal: VideoJobJournal,
) -> ProcessorOutput:
    fingerprint = fingerprint_video_short_audio_request(
        source_sha256=snapshot.sha256,
        model=audio.model,
    )
    saved = audio.short_state
    if saved is not None:
        if saved.request_fingerprint != fingerprint:
            raise ResumeStateError(
                "The saved short-audio result belongs to a different request.",
                code="RESUME_STATE_MISMATCH",
            ) from None
        if saved.no_speech:
            raise NoSpeechDetected(
                details={
                    "provider": "google",
                    "model": audio.model,
                    "provider_calls_attempted": 0,
                    "remote_file_deleted": saved.metadata.get(
                        "remote_file_deleted"
                    ),
                    "provider_client_closed": saved.metadata.get(
                        "provider_client_closed"
                    ),
                }
            ) from None
        metadata = dict(saved.metadata)
        metadata["current_run_provider_call_count"] = 0
        metadata["current_model_token_usage"] = ()
        return ProcessorOutput(
            media_type="audio",
            markdown=saved.markdown,
            status=saved.status,
            warnings=saved.warnings,
            metadata=metadata,
        )

    short_snapshot = ShortMP3Snapshot(
        path=snapshot.path,
        byte_size=snapshot.byte_size,
        sha256=snapshot.sha256,
        duration_seconds=snapshot.duration_seconds,
    )
    try:
        response = recognize_short_mp3(
            short_snapshot,
            prompt=AUDIO_TRANSCRIPTION_PROMPT,
            config=config,
        )
    except NoSpeechDetected as error:
        metadata = {
            "provider": "google",
            "model": audio.model,
            "provider_call_count": error.details.get("provider_calls_attempted", 1),
            "remote_file_deleted": error.details.get("remote_file_deleted"),
            "provider_client_closed": error.details.get("provider_client_closed"),
        }
        journal.persist_audio(
            VideoAudioState(
                state="ready",
                mode="short",
                interval_minutes=None,
                model=audio.model,
                artifact=audio.artifact,
                duration_seconds=audio.duration_seconds,
                short_state=VideoShortAudioState(
                    request_fingerprint=fingerprint,
                    markdown=None,
                    markdown_sha256=None,
                    status="partial",
                    warnings=("No recognizable speech was detected.",),
                    metadata=metadata,
                    no_speech=True,
                ),
            )
        )
        raise
    output = build_short_mp3_processor_output(short_snapshot, response, config=config)
    journal.persist_audio(
        VideoAudioState(
            state="ready",
            mode="short",
            interval_minutes=None,
            model=audio.model,
            artifact=audio.artifact,
            duration_seconds=audio.duration_seconds,
            short_state=VideoShortAudioState(
                request_fingerprint=fingerprint,
                markdown=output.markdown,
                markdown_sha256=hashlib.sha256(
                    output.markdown.encode("utf-8")
                ).hexdigest(),
                status=output.status,
                warnings=output.warnings,
                metadata=output.metadata,
            ),
        )
    )
    return output


def _validate_snapshot(audio: VideoAudioState, snapshot) -> None:
    assert audio.artifact is not None
    if (
        snapshot.byte_size != audio.artifact.byte_size
        or snapshot.sha256 != audio.artifact.sha256
        or snapshot.duration_seconds != audio.duration_seconds
    ):
        raise ResumeStateError(
            "The extracted video audio no longer matches the journal.",
            code="RESUME_STATE_MISMATCH",
        ) from None
