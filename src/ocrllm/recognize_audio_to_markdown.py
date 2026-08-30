"""Recognize caller-planned audio slices into one resumable Markdown file."""

from __future__ import annotations

from pathlib import Path

from .audio_slice import AudioSlice
from .providers.provider_model import ProviderModel
from .result import RecognitionResult


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
) -> RecognitionResult:
    """Settle explicit audio ranges through fixed provider lanes."""
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
            overwrite=overwrite,
        )
    except OCRLLMError as error:
        public_error = error
    clear_public_error(public_error)
    raise public_error from None
