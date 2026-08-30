"""Validate one caller-owned MP3 inside the ten-hour product boundary."""

from __future__ import annotations

import stat
from pathlib import Path

from ..detect_source_type import detect_source_type
from ..errors import InvalidSource
from .decode_mp3_duration import decode_mp3_duration
from .load_miniaudio import load_miniaudio
from .probe_long_mp3 import MAX_PRODUCT_AUDIO_DURATION_SECONDS


MAX_PRODUCT_MP3_SOURCE_BYTES = 2_000_000_000


def probe_product_mp3(source_path: Path) -> float:
    """Return decoded seconds without applying one provider's request limit."""
    source = Path(source_path)
    detect_source_type(source)
    try:
        source_stat = source.stat()
    except FileNotFoundError as error:
        raise InvalidSource(
            "The audio source does not exist.",
            code="SOURCE_NOT_FOUND",
        ) from error
    except ValueError as error:
        raise InvalidSource(
            "The audio source path is invalid.",
            code="SOURCE_INVALID",
        ) from error
    except OSError as error:
        raise InvalidSource(
            "The audio source cannot be inspected.",
            code="SOURCE_UNREADABLE",
        ) from error
    if not stat.S_ISREG(source_stat.st_mode) or source_stat.st_size <= 0:
        raise InvalidSource(
            "The audio source is not a nonempty regular file.",
            code="SOURCE_INVALID",
        ) from None
    if source_stat.st_size > MAX_PRODUCT_MP3_SOURCE_BYTES:
        raise InvalidSource(
            "The audio source exceeds the product MP3 byte limit.",
            code="SOURCE_TOO_LARGE",
            details={
                "byte_size": source_stat.st_size,
                "maximum_byte_size": MAX_PRODUCT_MP3_SOURCE_BYTES,
            },
        ) from None

    duration_seconds = decode_mp3_duration(source, backend=load_miniaudio())
    if duration_seconds > MAX_PRODUCT_AUDIO_DURATION_SECONDS:
        raise InvalidSource(
            "The MP3 source exceeds the ten-hour product limit.",
            code="SOURCE_TOO_LARGE",
            details={
                "decoded_duration_seconds": duration_seconds,
                "maximum_duration_seconds": MAX_PRODUCT_AUDIO_DURATION_SECONDS,
            },
        ) from None
    return duration_seconds
