"""Read one bounded image path once and validate those exact bytes."""

from __future__ import annotations

from pathlib import Path

from ..errors import OCRLLMError, InvalidSource
from ..validate_source import MAX_SOURCE_BYTES
from .decode_image_bytes import decode_image_bytes
from .decoded_image_info import DecodedImageInfo


def decode_image(source: str | Path) -> DecodedImageInfo:
    """Read one path once, then verify and fully decode the captured bytes."""
    source_path = Path(source)
    image_bytes = _read_image_bytes_bounded(source_path)
    return decode_image_bytes(image_bytes, suffix=source_path.suffix)


def _read_image_bytes_bounded(source_path: Path) -> bytes:
    try:
        source_stream = source_path.open("rb")
    except (ValueError, MemoryError, OSError) as error:
        raise _map_image_source_access_error(error) from None

    primary_error: BaseException | None = None
    try:
        try:
            image_bytes = source_stream.read(MAX_SOURCE_BYTES + 1)
        except (ValueError, MemoryError, OSError) as error:
            raise _map_image_source_access_error(error) from None
    except BaseException as error:
        primary_error = error
        raise
    finally:
        _close_bounded_image_stream(
            source_stream,
            primary_error=primary_error,
        )

    if not image_bytes:
        raise InvalidSource(
            "The image source is empty.",
            code="SOURCE_INVALID",
        ) from None
    if len(image_bytes) > MAX_SOURCE_BYTES:
        raise InvalidSource(
            "The image source exceeds the 25 MiB safety limit.",
            code="SOURCE_TOO_LARGE",
        ) from None
    return image_bytes


def _close_bounded_image_stream(
    source_stream,
    *,
    primary_error: BaseException | None,
) -> None:
    """Close the bounded image stream without replacing an active failure."""

    try:
        source_stream.close()
    except (ValueError, MemoryError, OSError) as error:
        if primary_error is None:
            raise _map_image_source_access_error(error) from None
        if isinstance(primary_error, OCRLLMError):
            primary_error._add_safe_detail("source_stream_cleanup_failed", True)


def _map_image_source_access_error(
    error: OSError | ValueError | MemoryError,
) -> InvalidSource:
    """Map one expected image-file access failure without retaining its data."""

    if isinstance(error, FileNotFoundError):
        return InvalidSource(
            "The image source is no longer available.",
            code="SOURCE_NOT_FOUND",
        )
    if isinstance(error, ValueError):
        return InvalidSource(
            "The image source path is invalid.",
            code="SOURCE_INVALID",
        )
    if isinstance(error, MemoryError):
        return InvalidSource(
            "The image source could not be read within safe memory limits.",
            code="SOURCE_TOO_LARGE",
        )
    return InvalidSource(
        "The image source could not be read.",
        code="SOURCE_UNREADABLE",
    )
