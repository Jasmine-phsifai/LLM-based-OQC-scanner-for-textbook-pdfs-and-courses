"""Create one request-owned MP4 snapshot beside its output root."""

from __future__ import annotations

import atexit
import os
import shutil
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ..errors import (
    InvalidSource,
    OCRLLMError,
    OutputError,
    UnsupportedFormat,
)


_COPY_CHUNK_BYTES = 1024 * 1024


@contextmanager
def snapshot_video_source(
    source_path: Path,
    *,
    snapshot_parent: Path,
) -> Iterator[Path]:
    """Yield one disk-backed MP4 copy whose bytes belong to this request."""
    source = Path(source_path)
    _validate_mp4_suffix(source)
    source_stream = _open_video_source(source)
    snapshot_root: Path | None = None
    primary_error: BaseException | None = None
    try:
        source_error: BaseException | None = None
        try:
            expected_size = _opened_video_size(source_stream)
            _prepare_snapshot_parent(snapshot_parent)
            try:
                snapshot_root = Path(
                    tempfile.mkdtemp(
                        prefix=".ocrllm-video-source-",
                        dir=snapshot_parent,
                    )
                )
            except (OSError, ValueError) as error:
                raise OutputError(
                    "A temporary video-snapshot directory could not be created.",
                    code="OUTPUT_WRITE_FAILED",
                ) from error
            snapshot_path = snapshot_root / "source.mp4"
            _copy_open_video(
                source_stream,
                snapshot_path,
                expected_size=expected_size,
            )
        except BaseException as error:
            source_error = error
            raise
        finally:
            _close_video_source(source_stream, primary_error=source_error)

        yield snapshot_path
    except BaseException as error:
        primary_error = error
        raise
    finally:
        if snapshot_root is not None:
            try:
                _delete_video_snapshot(snapshot_root)
            except OutputError:
                if primary_error is None:
                    raise
                if isinstance(primary_error, OCRLLMError):
                    primary_error._add_safe_detail(
                        "video_snapshot_cleanup_failed",
                        True,
                    )


def _validate_mp4_suffix(source_path: Path) -> None:
    suffix = source_path.suffix.casefold()
    if suffix == ".mp4":
        return
    raise UnsupportedFormat(
        "Video recognition currently accepts exactly one MP4 source.",
        details={"extension": suffix or None},
    ) from None


def _open_video_source(source_path: Path):
    try:
        return source_path.open("rb")
    except FileNotFoundError as error:
        raise InvalidSource(
            "The video source does not exist.",
            code="SOURCE_NOT_FOUND",
        ) from error
    except (OSError, ValueError) as error:
        raise InvalidSource(
            "The video source could not be opened for snapshotting.",
            code="SOURCE_UNREADABLE",
        ) from error


def _opened_video_size(source_stream) -> int:
    try:
        source_stat = os.fstat(source_stream.fileno())
    except (OSError, ValueError) as error:
        raise InvalidSource(
            "The opened video source could not be inspected.",
            code="SOURCE_UNREADABLE",
        ) from error
    if not stat.S_ISREG(source_stat.st_mode):
        raise InvalidSource(
            "The video source must be a regular file.",
            code="SOURCE_INVALID",
        ) from None
    if source_stat.st_size <= 0:
        raise InvalidSource(
            "The video source must be nonempty.",
            code="SOURCE_INVALID",
        ) from None
    return source_stat.st_size


def _prepare_snapshot_parent(snapshot_parent: Path) -> None:
    try:
        snapshot_parent.mkdir(parents=True, exist_ok=True)
        if not snapshot_parent.is_dir():
            raise OutputError(
                "The video output parent must be a directory.",
                code="OUTPUT_PATH_INVALID",
            ) from None
    except OutputError:
        raise
    except (OSError, ValueError) as error:
        raise OutputError(
            "The video output parent could not be created.",
            code="OUTPUT_PATH_INVALID",
        ) from error


def _copy_open_video(
    source_stream,
    snapshot_path: Path,
    *,
    expected_size: int,
) -> None:
    try:
        snapshot_stream = snapshot_path.open("xb")
    except (OSError, ValueError) as error:
        raise OutputError(
            "A temporary video snapshot could not be created.",
            code="OUTPUT_WRITE_FAILED",
        ) from error

    copied_size = 0
    primary_error: BaseException | None = None
    try:
        while copied_size < expected_size:
            try:
                chunk = source_stream.read(
                    min(_COPY_CHUNK_BYTES, expected_size - copied_size)
                )
            except (OSError, ValueError) as error:
                raise InvalidSource(
                    "The video source could not be read completely.",
                    code="SOURCE_UNREADABLE",
                ) from error
            if not chunk:
                _raise_video_changed()
            copied_size += len(chunk)
            if copied_size > expected_size:
                _raise_video_changed()
            try:
                written_size = snapshot_stream.write(chunk)
            except (OSError, ValueError) as error:
                raise OutputError(
                    "A temporary video snapshot could not be written.",
                    code="OUTPUT_WRITE_FAILED",
                ) from error
            if written_size != len(chunk):
                raise OutputError(
                    "A temporary video snapshot could not be written completely.",
                    code="OUTPUT_WRITE_FAILED",
                ) from None

        try:
            if source_stream.read(1):
                _raise_video_changed()
        except (OSError, ValueError) as error:
            raise InvalidSource(
                "The video source could not be read completely.",
                code="SOURCE_UNREADABLE",
            ) from error

        try:
            snapshot_stream.flush()
            os.fsync(snapshot_stream.fileno())
        except (OSError, ValueError) as error:
            raise OutputError(
                "A temporary video snapshot could not be made durable.",
                code="OUTPUT_WRITE_FAILED",
            ) from error
    except BaseException as error:
        primary_error = error
        raise
    finally:
        _close_video_snapshot_stream(snapshot_stream, primary_error=primary_error)


def _close_video_source(source_stream, *, primary_error: BaseException | None) -> None:
    try:
        source_stream.close()
    except (OSError, ValueError):
        if primary_error is None:
            raise InvalidSource(
                "The opened video source could not be closed safely.",
                code="SOURCE_UNREADABLE",
            ) from None
        if isinstance(primary_error, OCRLLMError):
            primary_error._add_safe_detail("source_stream_cleanup_failed", True)


def _close_video_snapshot_stream(
    snapshot_stream,
    *,
    primary_error: BaseException | None,
) -> None:
    try:
        snapshot_stream.close()
    except (OSError, ValueError):
        if primary_error is None:
            raise OutputError(
                "The temporary video snapshot could not be closed safely.",
                code="OUTPUT_WRITE_FAILED",
            ) from None
        if isinstance(primary_error, OCRLLMError):
            primary_error._add_safe_detail("snapshot_stream_cleanup_failed", True)


def _raise_video_changed() -> None:
    raise InvalidSource(
        "The video source changed while it was being snapshotted.",
        code="SOURCE_INVALID",
    ) from None


def _delete_video_snapshot(snapshot_root: Path) -> None:
    try:
        shutil.rmtree(snapshot_root)
    except FileNotFoundError:
        return
    except OSError as error:
        atexit.register(shutil.rmtree, snapshot_root, ignore_errors=True)
        raise OutputError(
            "The request-owned video snapshot could not be removed.",
            code="OUTPUT_WRITE_FAILED",
        ) from error
