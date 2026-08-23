"""Validate one source path before optional decoders or providers run."""

from __future__ import annotations

import stat
from pathlib import Path

from .detect_source_type import detect_source_type
from .errors import OCRLLMError, InvalidSource


MAX_SOURCE_BYTES = 25 * 1024 * 1024


def validate_source(source: str | Path) -> int:
    """Validate one Phase 0 image source and return its byte size.

    This function owns filesystem validation only. Image structure and decoded
    dimensions are validated separately by ``decode_image``.
    """
    source_path = Path(source)
    detect_source_type(source_path)

    try:
        source_stat = source_path.stat()
    except FileNotFoundError as error:
        raise InvalidSource(
            "The recognition source does not exist.",
            code="SOURCE_NOT_FOUND",
        ) from error
    except ValueError as error:
        raise InvalidSource(
            "The recognition source path is invalid.",
            code="SOURCE_INVALID",
        ) from error
    except OSError as error:
        raise InvalidSource(
            "The recognition source cannot be inspected.",
            code="SOURCE_UNREADABLE",
        ) from error

    if not stat.S_ISREG(source_stat.st_mode):
        raise InvalidSource(
            "The recognition source is not a regular file.",
            code="SOURCE_INVALID",
        )
    if source_stat.st_size <= 0:
        raise InvalidSource(
            "The recognition source is empty.",
            code="SOURCE_INVALID",
        )
    if source_stat.st_size > MAX_SOURCE_BYTES:
        raise InvalidSource(
            "The recognition source exceeds the 25 MiB safety limit.",
            code="SOURCE_TOO_LARGE",
            details={"byte_size": source_stat.st_size, "maximum_byte_size": MAX_SOURCE_BYTES},
        )

    try:
        source_file = source_path.open("rb")
    except ValueError as error:
        raise InvalidSource(
            "The recognition source path is invalid.",
            code="SOURCE_INVALID",
        ) from error
    except OSError as error:
        raise InvalidSource(
            "The recognition source is not readable.",
            code="SOURCE_UNREADABLE",
        ) from error

    primary_error: BaseException | None = None
    try:
        try:
            first_byte = source_file.read(1)
        except ValueError as error:
            raise InvalidSource(
                "The recognition source path is invalid.",
                code="SOURCE_INVALID",
            ) from error
        except OSError as error:
            raise InvalidSource(
                "The recognition source is not readable.",
                code="SOURCE_UNREADABLE",
            ) from error
    except BaseException as error:
        primary_error = error
        raise
    finally:
        _close_source_stream(source_file, primary_error=primary_error)

    if not first_byte:
        raise InvalidSource(
            "The recognition source became empty while it was being validated.",
            code="SOURCE_INVALID",
        )
    return source_stat.st_size


def _close_source_stream(
    source_file,
    *,
    primary_error: BaseException | None,
) -> None:
    """Close the validation stream without replacing an active failure."""

    try:
        source_file.close()
    except (OSError, ValueError):
        if primary_error is None:
            raise InvalidSource(
                "The recognition source could not be closed safely.",
                code="SOURCE_UNREADABLE",
            ) from None
        if isinstance(primary_error, OCRLLMError):
            primary_error._add_safe_detail("source_stream_cleanup_failed", True)
