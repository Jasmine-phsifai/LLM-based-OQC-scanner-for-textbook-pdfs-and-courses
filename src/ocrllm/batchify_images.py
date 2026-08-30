"""Group an exact image tuple without hiding provider dispatch."""

from __future__ import annotations

from pathlib import Path

from .errors import ConfigError, InvalidSource
from .normalize_provider_model_lanes import normalize_provider_model_lanes
from .providers.provider_model import ProviderModel
from .validate_image_group import validate_image_group


def batchify_images(
    sources: tuple[str | Path, ...],
    *,
    batch_size: int | None = None,
    provider: (
        ProviderModel
        | list[ProviderModel]
        | list[list[ProviderModel]]
        | None
    ) = None,
) -> tuple[tuple[Path, ...], ...]:
    """Validate and group concrete images while preserving caller order."""
    if type(sources) is not tuple or not sources:
        raise InvalidSource(
            "batchify_images() requires a nonempty exact tuple of image sources.",
            code="SOURCE_INVALID",
        ) from None
    provider_lanes = (
        normalize_provider_model_lanes(
            provider,
            distinguish_runtime_settings=False,
        )
        if provider is not None
        else None
    )
    if batch_size is None:
        if provider_lanes is None:
            raise ConfigError(
                "batchify_images() requires batch_size or provider.",
                code="CONFIG_MISSING",
                details={"provider_calls_attempted": 0},
            ) from None
        candidates = tuple(
            candidate for lane in provider_lanes for candidate in lane
        )
        if any(not candidate.supports_plain_ocr for candidate in candidates):
            raise ConfigError(
                "Every selected ProviderModel must support image OCR.",
                code="CONFIG_INVALID",
                details={"provider_calls_attempted": 0},
            ) from None
        defaults = tuple(
            candidate.default_image_batch_size for candidate in candidates
        )
        assert all(value is not None for value in defaults)
        resolved_batch_size = min(value for value in defaults if value is not None)
    elif type(batch_size) is not int or batch_size <= 0:
        raise ConfigError(
            "batchify_images() batch_size must be a positive integer.",
            code="CONFIG_INVALID",
            details={"provider_calls_attempted": 0},
        ) from None
    else:
        resolved_batch_size = batch_size

    if any(not isinstance(source, (str, Path)) for source in sources):
        raise InvalidSource(
            "batchify_images() sources must contain only strings or Paths.",
            code="SOURCE_INVALID",
        ) from None
    paths = tuple(Path(source) for source in sources)
    groups = tuple(
        paths[index : index + resolved_batch_size]
        for index in range(0, len(paths), resolved_batch_size)
    )
    for group in groups:
        validate_image_group(group)
    return groups
