"""Create one bounded request-owned PDF snapshot."""

from __future__ import annotations

import atexit
import os
import shutil
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from ..errors import ConfigError, InvalidSource, OCRLLMError, OutputError


MAX_PDF_SOURCE_BYTES = 100 * 1024 * 1024
COPY_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True, slots=True)
class PDFSnapshot:
    """The fixed path and root owned for one PDF request."""

    path: Path
    root: Path
    byte_size: int


@contextmanager
def snapshot_pdf(
    source_path: Path,
    *,
    temp_dir: str | Path | None,
) -> Iterator[PDFSnapshot]:
    """Yield an exact PDF copy without loading the whole file into Python memory."""
    source = Path(source_path)
    source_stream = _open_validated_pdf(source)
    snapshot_root: Path | None = None
    primary_error: BaseException | None = None
    try:
        source_error: BaseException | None = None
        try:
            expected_size = _opened_pdf_size(source_stream)
            temporary_parent = _prepare_temporary_parent(temp_dir)
            try:
                snapshot_root = Path(
                    tempfile.mkdtemp(prefix="ocrllm-pdf-", dir=temporary_parent)
                )
            except (OSError, ValueError) as error:
                raise OutputError(
                    "A temporary PDF snapshot directory could not be created.",
                    code="OUTPUT_WRITE_FAILED",
                ) from error
            snapshot_path = snapshot_root / "source.pdf"
            copied_size = _copy_open_pdf(
                source_stream,
                snapshot_path,
                expected_size=expected_size,
            )
        except BaseException as error:
            source_error = error
            raise
        finally:
            _close_pdf_stream(source_stream, primary_error=source_error)

        yield PDFSnapshot(
            path=snapshot_path,
            root=snapshot_root,
            byte_size=copied_size,
        )
    except BaseException as error:
        primary_error = error
        raise
    finally:
        if snapshot_root is not None:
            try:
                shutil.rmtree(snapshot_root)
            except FileNotFoundError:
                pass
            except OSError:
                atexit.register(shutil.rmtree, snapshot_root, ignore_errors=True)
                if primary_error is None:
                    raise OutputError(
                        "The temporary PDF snapshot could not be removed.",
                        code="OUTPUT_WRITE_FAILED",
                    ) from None
                if isinstance(primary_error, OCRLLMError):
                    primary_error._add_safe_detail("pdf_snapshot_cleanup_failed", True)


def _open_validated_pdf(source_path: Path):
    if source_path.suffix.casefold() != ".pdf":
        raise InvalidSource(
            "The PDF source extension is invalid.",
            code="SOURCE_INVALID",
        ) from None
    try:
        source_stat = source_path.stat()
    except FileNotFoundError as error:
        raise InvalidSource(
            "The PDF source does not exist.",
            code="SOURCE_NOT_FOUND",
        ) from error
    except (OSError, ValueError) as error:
        raise InvalidSource(
            "The PDF source cannot be inspected.",
            code="SOURCE_UNREADABLE",
        ) from error
    _validate_pdf_stat(source_stat)
    try:
        return source_path.open("rb")
    except FileNotFoundError as error:
        raise InvalidSource(
            "The PDF source disappeared before it could be snapshotted.",
            code="SOURCE_NOT_FOUND",
        ) from error
    except (OSError, ValueError) as error:
        raise InvalidSource(
            "The PDF source could not be opened.",
            code="SOURCE_UNREADABLE",
        ) from error


def _opened_pdf_size(source_stream) -> int:
    try:
        source_stat = os.fstat(source_stream.fileno())
    except (OSError, ValueError) as error:
        raise InvalidSource(
            "The opened PDF source could not be inspected.",
            code="SOURCE_UNREADABLE",
        ) from error
    return _validate_pdf_stat(source_stat)


def _validate_pdf_stat(source_stat: os.stat_result) -> int:
    if not stat.S_ISREG(source_stat.st_mode):
        raise InvalidSource(
            "The PDF source is not a regular file.",
            code="SOURCE_INVALID",
        ) from None
    if source_stat.st_size <= 0:
        raise InvalidSource("The PDF source is empty.", code="SOURCE_INVALID") from None
    if source_stat.st_size > MAX_PDF_SOURCE_BYTES:
        raise InvalidSource(
            "The PDF source exceeds the 100 MiB safety limit.",
            code="SOURCE_TOO_LARGE",
            details={
                "byte_size": source_stat.st_size,
                "maximum_byte_size": MAX_PDF_SOURCE_BYTES,
            },
        ) from None
    return source_stat.st_size


def _copy_open_pdf(source_stream, snapshot_path: Path, *, expected_size: int) -> int:
    try:
        snapshot_stream = snapshot_path.open("xb")
    except (OSError, ValueError) as error:
        raise OutputError(
            "A temporary PDF snapshot could not be created.",
            code="OUTPUT_WRITE_FAILED",
        ) from error
    copied_size = 0
    primary_error: BaseException | None = None
    try:
        while copied_size < expected_size:
            try:
                chunk = source_stream.read(
                    min(COPY_CHUNK_BYTES, expected_size - copied_size)
                )
            except (OSError, ValueError) as error:
                raise InvalidSource(
                    "The PDF source could not be read completely.",
                    code="SOURCE_UNREADABLE",
                ) from error
            if not chunk:
                _raise_pdf_changed()
            copied_size += len(chunk)
            if copied_size > expected_size:
                _raise_pdf_changed()
            try:
                written_size = snapshot_stream.write(chunk)
            except (OSError, ValueError) as error:
                raise OutputError(
                    "A temporary PDF snapshot could not be written.",
                    code="OUTPUT_WRITE_FAILED",
                ) from error
            if written_size != len(chunk):
                raise OutputError(
                    "A temporary PDF snapshot could not be written completely.",
                    code="OUTPUT_WRITE_FAILED",
                ) from None
        try:
            extra_byte = source_stream.read(1)
        except (OSError, ValueError) as error:
            raise InvalidSource(
                "The PDF source could not be read completely.",
                code="SOURCE_UNREADABLE",
            ) from error
        if extra_byte:
            _raise_pdf_changed()
        try:
            snapshot_stream.flush()
            os.fsync(snapshot_stream.fileno())
        except (OSError, ValueError) as error:
            raise OutputError(
                "A temporary PDF snapshot could not be made durable.",
                code="OUTPUT_WRITE_FAILED",
            ) from error
    except BaseException as error:
        primary_error = error
        raise
    finally:
        _close_snapshot_stream(snapshot_stream, primary_error=primary_error)
    return copied_size


def _close_pdf_stream(source_stream, *, primary_error: BaseException | None) -> None:
    try:
        source_stream.close()
    except (OSError, ValueError):
        if primary_error is None:
            raise InvalidSource(
                "The opened PDF source could not be closed safely.",
                code="SOURCE_UNREADABLE",
            ) from None
        if isinstance(primary_error, OCRLLMError):
            primary_error._add_safe_detail("source_stream_cleanup_failed", True)


def _close_snapshot_stream(snapshot_stream, *, primary_error: BaseException | None) -> None:
    try:
        snapshot_stream.close()
    except (OSError, ValueError):
        if primary_error is None:
            raise OutputError(
                "The temporary PDF snapshot could not be closed safely.",
                code="OUTPUT_WRITE_FAILED",
            ) from None
        if isinstance(primary_error, OCRLLMError):
            primary_error._add_safe_detail("snapshot_stream_cleanup_failed", True)


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


def _raise_pdf_changed() -> None:
    raise InvalidSource(
        "The PDF source changed while it was being snapshotted.",
        code="SOURCE_INVALID",
    ) from None
