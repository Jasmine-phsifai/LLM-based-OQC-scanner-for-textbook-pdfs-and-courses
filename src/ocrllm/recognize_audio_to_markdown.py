"""Recognize caller-planned audio slices into one resumable Markdown file."""

from __future__ import annotations

from .observe_recognition import observed_stage

from pathlib import Path

from .audio_slice import AudioSlice
from .audio_gap_policy import AudioGapPolicy
from .providers.provider_model import ProviderModel
from .result import RecognitionResult


@observed_stage('recognize', 'asr')
def recognize_audio_to_markdown(
    slices: tuple[AudioSlice, ...],
    *,
    provider: (
        ProviderModel
        | list[ProviderModel]
        | list[list[ProviderModel]]
    ),
    output_path: str | Path | None = None,
    timeout_seconds: float = 120.0,
    overwrite: bool = False,
    failed_slice_minutes: int | None = None,
    audio_gap_policy: AudioGapPolicy | None = None,
) -> RecognitionResult:
    """Settle explicit audio ranges through fixed provider lanes.

    Opt-in failed_slice_minutes subdivides a range once when the service reports
    the proven output_token_limit machine code. Other failures remain explicit;
    provider defaults and the caller's original slice plan are unchanged.
    Explicit audio_gap_policy persists bounded output-limit attempts and permits
    complete_with_gaps only within caller limits after three same-identity
    failures. Accepted jobs retain their checkpoint; ordinary resume returns
    all gap metadata without provider calls, rebuilding a missing MD if needed.
    """
    from .clear_public_error import clear_public_error
    from .errors import OCRLLMError
    from .run_merged_audio_job import run_merged_audio_job

    public_error: OCRLLMError | None = None
    try:
        return run_merged_audio_job(
            slices,
            provider=provider,
            output_path=output_path,
            timeout_seconds=timeout_seconds,
            resume=False,
            failed_slice_minutes=failed_slice_minutes,
            audio_gap_policy=audio_gap_policy,
            overwrite=overwrite,
        )
    except OCRLLMError as error:
        public_error = error
    clear_public_error(public_error)
    raise public_error from None
