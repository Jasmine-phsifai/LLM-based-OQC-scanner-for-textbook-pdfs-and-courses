"""Resume unresolved slices in one merged-audio Markdown job."""

from __future__ import annotations

from pathlib import Path

from .audio_slice import AudioSlice
from .audio_gap_policy import AudioGapPolicy
from .providers.provider_model import ProviderModel
from .result import RecognitionResult


def resume_audio_to_markdown(
    slices: tuple[AudioSlice, ...],
    *,
    provider: (
        ProviderModel
        | list[ProviderModel]
        | list[list[ProviderModel]]
    ),
    output_path: str | Path | None = None,
    timeout_seconds: float = 120.0,
    failed_slice_minutes: int | None = None,
    audio_gap_policy: AudioGapPolicy | None = None,
    only_output_limit: bool = False,
) -> RecognitionResult:
    """Restore the original plan, optionally subdividing its failed ranges.

    failed_slice_minutes explicitly plans smaller children only for failed slots;
    existing settled parents/children stay reusable. Subsequent ordinary resume
    needs no special option to reuse those children. For continued unattended
    recovery, pass the same interval with only_output_limit=True: saved budget
    failures subdivide before dispatch and later budget failures subdivide once.
    This is a bounded subdivision, not a retry loop.
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
            resume=True,
            failed_slice_minutes=failed_slice_minutes,
            audio_gap_policy=audio_gap_policy,
            only_output_limit=only_output_limit,
            overwrite=True,
        )
    except OCRLLMError as error:
        public_error = error
    clear_public_error(public_error)
    raise public_error from None
