"""Group an exact image tuple without hiding provider dispatch."""

from __future__ import annotations

from pathlib import Path

from .errors import ConfigError, InvalidSource
from .providers.provider_model import ProviderModel
from .validate_image_group import validate_image_group


def batchify_images(
    sources: tuple[str | Path, ...],
    *,
    batch_size: int | None = None,
    provider: ProviderModel | None = None,
) -> tuple[tuple[Path, ...], ...]:
    """Validate and group concrete images while preserving caller order."""
    if type(sources) is not tuple or not sources:
        raise InvalidSource(
            "batchify_images() requires a nonempty exact tuple of image sources.",
            code="SOURCE_INVALID",
        ) from None
    if provider is not None and type(provider) is not ProviderModel:
        raise ConfigError(
            "batchify_images() provider must be an exact ProviderModel.",
            code="CONFIG_INVALID",
            details={"provider_calls_attempted": 0},
        ) from None
    if batch_size is None:
        if provider is None:
            raise ConfigError(
                "batchify_images() requires batch_size or provider.",
                code="CONFIG_MISSING",
                details={"provider_calls_attempted": 0},
            ) from None
        if not provider.supports_plain_ocr:
            raise ConfigError(
                "The selected ProviderModel does not support image OCR.",
                code="CONFIG_INVALID",
                details={"provider_calls_attempted": 0},
            ) from None
        resolved_batch_size = provider.default_image_batch_size
        assert resolved_batch_size is not None
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
