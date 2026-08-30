"""Repair strict failed audio ranges without restoring split parameters."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .providers.provider_model import ProviderModel
from .result import RecognitionResult


_ProviderInput = (
    ProviderModel
    | list[ProviderModel]
    | list[list[ProviderModel]]
)


def repair_audio_to_markdown(
    source: str | Path,
    *,
    provider: _ProviderInput,
    output_path: str | Path | None = None,
    timeout_seconds: float = 120.0,
) -> RecognitionResult:
    """Repair current failed interval headings for one explicit MP3 source."""
    from .audio.snapshot_product_mp3 import snapshot_product_mp3
    from .clear_public_error import clear_public_error
    from .config import Config
    from .errors import InvalidSource, OCRLLMError, OutputError
    from .normalize_provider_model_lanes import normalize_provider_model_lanes
    from .output.claim_output_target import claim_output_target
    from .output.resolve_merged_audio_output_path import (
        resolve_merged_audio_output_path,
    )
    from .output.resolve_resume_state_path import resolve_resume_state_path
    from .parse_merged_audio_failure_markers import (
        parse_merged_audio_failure_markers,
    )
    from .providers.validate_audio_provider_model import validate_audio_provider_model
    from .read_repair_markdown import read_repair_markdown
    from .repair_marked_audio_ranges import repair_marked_audio_ranges

    public_error: OCRLLMError | None = None
    try:
        provider_lanes = normalize_provider_model_lanes(
            provider,
            distinguish_runtime_settings=True,
        )
        for candidate in (
            candidate for lane in provider_lanes for candidate in lane
        ):
            validate_audio_provider_model(candidate)
        config = Config(timeout_seconds=timeout_seconds)
        if not isinstance(source, (str, Path)):
            raise InvalidSource(
                "Audio repair source must be a string or Path.",
                code="SOURCE_INVALID",
                details={"provider_calls_attempted": 0},
            ) from None
        source_path = Path(source)
        resolved_output_path = resolve_merged_audio_output_path(
            source_path,
            output_path=output_path,
        )
        state_path = resolve_resume_state_path(resolved_output_path)
        with claim_output_target(resolved_output_path):
            markdown = read_repair_markdown(
                resolved_output_path,
                state_path=state_path,
            )
            result: RecognitionResult | None = None
            try:
                with snapshot_product_mp3(source_path) as snapshot:
                    slot_count, markers = parse_merged_audio_failure_markers(
                        markdown,
                        duration_seconds=snapshot.duration_seconds,
                    )
                    result = repair_marked_audio_ranges(
                        snapshot=snapshot,
                        slot_count=slot_count,
                        markers=markers,
                        markdown=markdown,
                        provider_lanes=provider_lanes,
                        output_path=resolved_output_path,
                        config=config,
                    )
            except OutputError:
                if result is None:
                    raise
                result = replace(
                    result,
                    warnings=(
                        *result.warnings,
                        "The temporary audio source snapshot could not be removed "
                        "after repair.",
                    ),
                )
            assert result is not None
            return result
    except OCRLLMError as error:
        public_error = error
    clear_public_error(public_error)
    raise public_error from None
