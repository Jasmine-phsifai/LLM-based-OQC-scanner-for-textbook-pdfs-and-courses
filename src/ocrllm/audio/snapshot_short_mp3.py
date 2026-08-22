"""Create one bounded, validated, request-owned short-MP3 snapshot."""

from __future__ import annotations

import atexit
import os
import shutil
import stat
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from ..errors import (
    ConfigError,
    InvalidSource,
    OCRLLMError,
    OutputError,
    UnsupportedFormat,
)
from .probe_short_mp3 import probe_short_mp3


MAX_SHORT_MP3_SOURCE_BYTES = 25 * 1024 * 1024
COPY_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True, slots=True)
class ShortMP3Snapshot:
    """Owned MP3 path plus validation facts needed by the future A1 caller."""

    path: Path
    byte_size: int
    duration_seconds: float


@contextmanager
def snapshot_short_mp3(
    source_path: Path,
    *,
    temp_dir: str | Path | None,
) -> Iterator[ShortMP3Snapshot]:
    """Yield one validated snapshot whose bytes no longer depend on the caller."""

    source = Path(source_path)
    _validate_mp3_suffix(source)
    _validate_source_path(source)
    source_stream = _open_source(source)

    with source_stream:
        source_size = _opened_source_size(source_stream)
        temporary_parent = _prepare_temporary_parent(temp_dir)
        try:
            snapshot_root = Path(
                tempfile.mkdtemp(prefix="ocrllm-audio-", dir=temporary_parent)
            )
        except (OSError, ValueError) as error:
            raise OutputError(
                "A temporary audio-snapshot directory could not be created.",
                code="OUTPUT_WRITE_FAILED",
            ) from error

        try:
            snapshot_path = snapshot_root / "source.mp3"
            copied_size = _copy_open_source(
                source_stream,
                snapshot_path,
                expected_size=source_size,
            )
            duration_seconds = probe_short_mp3(snapshot_path)
            yield ShortMP3Snapshot(
                path=snapshot_path,
                byte_size=copied_size,
                duration_seconds=duration_seconds,
            )
        finally:
            active_error = sys.exc_info()[1]
            try:
                _delete_snapshot_directory(snapshot_root)
            except OutputError:
                if active_error is None:
                    raise
                if isinstance(active_error, OCRLLMError):
                    active_error._add_safe_detail("snapshot_cleanup_failed", True)


def _validate_mp3_suffix(source_path: Path) -> None:
    suffix = source_path.suffix.casefold()
    if suffix == ".mp3":
        return
    message = (
        "The audio source has no file extension."
        if not suffix
        else "The audio source extension is not supported."
    )
    raise UnsupportedFormat(
        message,
        details={"extension": suffix or None},
    ) from None


def _validate_source_path(source_path: Path) -> None:
    try:
        source_stat = source_path.stat()
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

    _validate_source_stat(source_stat)


def _validate_source_stat(source_stat: os.stat_result) -> int:
    if not stat.S_ISREG(source_stat.st_mode):
        raise InvalidSource(
            "The audio source is not a regular file.",
            code="SOURCE_INVALID",
        ) from None
    if source_stat.st_size <= 0:
        raise InvalidSource(
            "The audio source is empty.",
            code="SOURCE_INVALID",
        ) from None
    if source_stat.st_size > MAX_SHORT_MP3_SOURCE_BYTES:
        raise InvalidSource(
            "The audio source exceeds the 25 MiB local safety limit.",
            code="SOURCE_TOO_LARGE",
            details={
                "byte_size": source_stat.st_size,
                "maximum_byte_size": MAX_SHORT_MP3_SOURCE_BYTES,
            },
        ) from None
    return source_stat.st_size


def _open_source(source_path: Path):
    try:
        return source_path.open("rb")
    except FileNotFoundError as error:
        raise InvalidSource(
            "The audio source disappeared before it could be snapshotted.",
            code="SOURCE_NOT_FOUND",
        ) from error
    except (OSError, ValueError) as error:
        raise InvalidSource(
            "The audio source could not be opened for snapshotting.",
            code="SOURCE_UNREADABLE",
        ) from error


def _opened_source_size(source_stream) -> int:
    try:
        source_stat = os.fstat(source_stream.fileno())
    except (OSError, ValueError) as error:
        raise InvalidSource(
            "The opened audio source could not be inspected.",
            code="SOURCE_UNREADABLE",
        ) from error
    return _validate_source_stat(source_stat)


def _prepare_temporary_parent(configured_parent: str | Path | None) -> Path | None:
    if configured_parent is None:
        return None
    parent = Path(configured_parent)
    try:
        if parent.exists() and not parent.is_dir():
            raise ConfigError(
                "Config.temp_dir must identify a directory.",
                code="CONFIG_INVALID",
            )
        parent.mkdir(parents=True, exist_ok=True)
    except ConfigError:
        raise
    except (OSError, ValueError) as error:
        raise ConfigError(
            "Config.temp_dir could not be created or opened.",
            code="CONFIG_INVALID",
        ) from error
    return parent


def _copy_open_source(
    source_stream,
    snapshot_path: Path,
    *,
    expected_size: int,
) -> int:
    try:
        snapshot_stream = snapshot_path.open("xb")
    except (OSError, ValueError) as error:
        raise OutputError(
            "A temporary audio snapshot could not be created.",
            code="OUTPUT_WRITE_FAILED",
        ) from error

    copied_size = 0
    with snapshot_stream:
        while copied_size < expected_size:
            read_size = min(COPY_CHUNK_BYTES, expected_size - copied_size)
            try:
                chunk = source_stream.read(read_size)
            except (OSError, ValueError) as error:
                raise InvalidSource(
                    "The audio source could not be read completely.",
                    code="SOURCE_UNREADABLE",
                ) from error
            if not chunk:
                _raise_source_changed()
            copied_size += len(chunk)
            if copied_size > expected_size:
                _raise_source_changed()
            try:
                snapshot_stream.write(chunk)
            except (OSError, ValueError) as error:
                raise OutputError(
                    "A temporary audio snapshot could not be written.",
                    code="OUTPUT_WRITE_FAILED",
                ) from error

        try:
            if source_stream.read(1):
                _raise_source_changed()
        except (OSError, ValueError) as error:
            raise InvalidSource(
                "The audio source could not be read completely.",
                code="SOURCE_UNREADABLE",
            ) from error

        try:
            snapshot_stream.flush()
            os.fsync(snapshot_stream.fileno())
        except (OSError, ValueError) as error:
            raise OutputError(
                "A temporary audio snapshot could not be made durable.",
                code="OUTPUT_WRITE_FAILED",
            ) from error
    return copied_size


def _raise_source_changed() -> None:
    raise InvalidSource(
        "The recognition source changed while it was being snapshotted.",
        code="SOURCE_INVALID",
    ) from None


def _delete_snapshot_directory(snapshot_root: Path) -> None:
    try:
        shutil.rmtree(snapshot_root)
    except FileNotFoundError:
        return
    except OSError as error:
        atexit.register(shutil.rmtree, snapshot_root, ignore_errors=True)
        raise OutputError(
            "The validated audio snapshot could not be removed after use.",
            code="OUTPUT_WRITE_FAILED",
        ) from error
