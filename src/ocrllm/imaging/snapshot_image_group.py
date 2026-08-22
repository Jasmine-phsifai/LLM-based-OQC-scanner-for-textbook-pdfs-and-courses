"""Create bounded validated snapshots for one provider image request."""

from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from ..config import Config
from ..errors import ConfigError, InvalidSource, OCRLLMError, OutputError
from ..validate_image_group import (
    MAX_AGGREGATE_SOURCE_BYTES,
    MAX_IMAGE_GROUP_COUNT,
    validate_image_group,
)
from ..validate_source import MAX_SOURCE_BYTES, validate_source


COPY_CHUNK_BYTES = 1024 * 1024


@contextmanager
def snapshot_image_group(
    sources: Sequence[Path],
    *,
    config: Config,
) -> Iterator[tuple[Path, ...]]:
    """Yield provider paths whose bytes cannot change with the caller's sources."""
    source_paths = tuple(Path(source) for source in sources)
    if len(source_paths) > MAX_IMAGE_GROUP_COUNT:
        raise InvalidSource(
            "An image group exceeds the 10-image safety limit.",
            code="SOURCE_TOO_LARGE",
        )

    byte_sizes = tuple(validate_source(source) for source in source_paths)
    if sum(byte_sizes) > MAX_AGGREGATE_SOURCE_BYTES:
        raise InvalidSource(
            "The image group exceeds the 100 MiB aggregate source limit.",
            code="SOURCE_TOO_LARGE",
        )

    temporary_parent = _prepare_temporary_parent(config.temp_dir)
    try:
        snapshot_root = Path(
            tempfile.mkdtemp(prefix="ocrllm-images-", dir=temporary_parent)
        )
    except (OSError, ValueError) as error:
        raise OutputError(
            "A temporary image-snapshot directory could not be created.",
            code="OUTPUT_WRITE_FAILED",
        ) from error

    try:
        snapshot_paths: list[Path] = []
        aggregate_bytes = 0
        for index, source_path in enumerate(source_paths):
            snapshot_parent = snapshot_root / f"{index:04d}"
            try:
                snapshot_parent.mkdir()
            except (OSError, ValueError) as error:
                raise OutputError(
                    "A temporary image-snapshot directory could not be prepared.",
                    code="OUTPUT_WRITE_FAILED",
                ) from error
            snapshot_path = snapshot_parent / source_path.name
            copied_bytes = _copy_source_bounded(
                source_path,
                snapshot_path,
                aggregate_bytes=aggregate_bytes,
            )
            aggregate_bytes += copied_bytes
            snapshot_paths.append(snapshot_path)

        validated_paths = tuple(snapshot_paths)
        validate_image_group(validated_paths)
        yield validated_paths
    finally:
        active_error = sys.exc_info()[1]
        try:
            _delete_snapshot_directory(snapshot_root)
        except OutputError:
            if active_error is None:
                raise
            if isinstance(active_error, OCRLLMError):
                active_error._add_safe_detail("snapshot_cleanup_failed", True)


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


def _copy_source_bounded(
    source_path: Path,
    snapshot_path: Path,
    *,
    aggregate_bytes: int,
) -> int:
    try:
        source_stream = source_path.open("rb")
    except FileNotFoundError as error:
        raise InvalidSource(
            "The recognition source disappeared before it could be snapshotted.",
            code="SOURCE_NOT_FOUND",
        ) from error
    except (OSError, ValueError) as error:
        raise InvalidSource(
            "The recognition source could not be read into a validated snapshot.",
            code="SOURCE_UNREADABLE",
        ) from error

    copied_bytes = 0
    with source_stream:
        try:
            snapshot_stream = snapshot_path.open("xb")
        except (OSError, ValueError) as error:
            raise OutputError(
                "A temporary image snapshot could not be created.",
                code="OUTPUT_WRITE_FAILED",
            ) from error

        with snapshot_stream:
            while True:
                try:
                    chunk = source_stream.read(COPY_CHUNK_BYTES)
                except (OSError, ValueError) as error:
                    raise InvalidSource(
                        "The recognition source could not be read completely.",
                        code="SOURCE_UNREADABLE",
                    ) from error
                if not chunk:
                    break
                copied_bytes += len(chunk)
                if copied_bytes > MAX_SOURCE_BYTES:
                    raise InvalidSource(
                        "The recognition source grew beyond the 25 MiB safety limit.",
                        code="SOURCE_TOO_LARGE",
                    )
                if aggregate_bytes + copied_bytes > MAX_AGGREGATE_SOURCE_BYTES:
                    raise InvalidSource(
                        "The image group grew beyond the 100 MiB aggregate source limit.",
                        code="SOURCE_TOO_LARGE",
                    )
                try:
                    written_size = snapshot_stream.write(chunk)
                except (OSError, ValueError) as error:
                    raise OutputError(
                        "A temporary image snapshot could not be written.",
                        code="OUTPUT_WRITE_FAILED",
                    ) from error
                if written_size != len(chunk):
                    raise OutputError(
                        "A temporary image snapshot could not be written completely.",
                        code="OUTPUT_WRITE_FAILED",
                    ) from None

            if copied_bytes == 0:
                raise InvalidSource(
                    "The recognition source became empty before it could be snapshotted.",
                    code="SOURCE_INVALID",
                )
            try:
                snapshot_stream.flush()
                os.fsync(snapshot_stream.fileno())
            except (OSError, ValueError) as error:
                raise OutputError(
                    "A temporary image snapshot could not be made durable.",
                    code="OUTPUT_WRITE_FAILED",
                ) from error
    return copied_bytes


def _delete_snapshot_directory(snapshot_root: Path) -> None:
    try:
        shutil.rmtree(snapshot_root)
    except FileNotFoundError:
        return
    except OSError as error:
        atexit.register(shutil.rmtree, snapshot_root, ignore_errors=True)
        raise OutputError(
            "Validated image snapshots could not be removed after provider use.",
            code="OUTPUT_WRITE_FAILED",
        ) from error
