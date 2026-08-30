"""Route one already-extracted media plan to its ordinary resume owner."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, overload

from .audio_slice import AudioSlice
from .errors import ConfigError, InvalidSource
from .providers.provider_model import ProviderModel
from .result import RecognitionResult


_ProviderInput = (
    ProviderModel
    | list[ProviderModel]
    | list[list[ProviderModel]]
)


@overload
def resume_video(
    source: tuple[tuple[str | Path, ...], ...],
    *,
    media_type: Literal["image"],
    providers: _ProviderInput,
    output_path: str | Path | None = None,
) -> RecognitionResult: ...


@overload
def resume_video(
    source: tuple[AudioSlice, ...],
    *,
    media_type: Literal["audio"],
    providers: _ProviderInput,
    output_path: str | Path | None = None,
) -> RecognitionResult: ...


def resume_video(
    source: object,
    *,
    media_type: str,
    providers: _ProviderInput,
    output_path: str | Path | None = None,
) -> RecognitionResult:
    """Delegate exactly one explicit image or audio resume operation."""
    if type(media_type) is not str or media_type not in {"image", "audio"}:
        raise ConfigError(
            "media_type must be exactly 'image' or 'audio'.",
            code="CONFIG_INVALID",
            details={"provider_calls_attempted": 0},
        ) from None
    if media_type == "image":
        if (
            type(source) is not tuple
            or not source
            or any(type(batch) is not tuple or not batch for batch in source)
            or any(
                any(not isinstance(item, (str, Path)) for item in batch)
                for batch in source
            )
        ):
            raise InvalidSource(
                "Image resume requires exact nonempty batches.",
                code="SOURCE_INVALID",
                details={"provider_calls_attempted": 0},
            ) from None
        from .resume_images_to_markdown import resume_images_to_markdown

        return resume_images_to_markdown(
            source,
            provider=providers,
            output_path=output_path,
        )

    if (
        type(source) is not tuple
        or not source
        or any(type(item) is not AudioSlice for item in source)
    ):
        raise InvalidSource(
            "Audio resume requires an exact AudioSlice tuple.",
            code="SOURCE_INVALID",
            details={"provider_calls_attempted": 0},
        ) from None
    from .resume_audio_to_markdown import resume_audio_to_markdown

    return resume_audio_to_markdown(
        source,
        provider=providers,
        output_path=output_path,
    )
