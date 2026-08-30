"""Resume unresolved slices in one merged-audio Markdown job."""

from __future__ import annotations

from pathlib import Path

from .audio_slice import AudioSlice
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
) -> RecognitionResult:
    """Restore one exact audio plan and resume through fixed lanes."""
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
            overwrite=True,
        )
    except OCRLLMError as error:
        public_error = error
    clear_public_error(public_error)
    raise public_error from None
