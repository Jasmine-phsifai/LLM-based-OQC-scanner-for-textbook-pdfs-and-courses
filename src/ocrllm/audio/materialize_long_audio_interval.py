"""Materialize one temporary MP3 from one planned long-audio interval."""

from __future__ import annotations

import math
import os
import stat
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ..errors import DependencyMissing, InvalidSource, OCRLLMError, OutputError
from .build_long_audio_interval_windows import LongAudioIntervalWindow
from .load_audio_ffmpeg_executable import load_audio_ffmpeg_executable


_MINIMUM_FFMPEG_TIMEOUT_SECONDS = 600
_FFMPEG_TIMEOUT_PADDING_SECONDS = 300


@contextmanager
def materialize_long_audio_interval(
    owned_source_path: Path,
    *,
    window: LongAudioIntervalWindow,
) -> Iterator[Path]:
    """Yield one mono 16 kHz MP3 beside an already request-owned source."""
    _validate_interval_window(window)
    source = Path(owned_source_path)
    executable = load_audio_ffmpeg_executable()
    segment_path = _create_interval_path(source.parent, index=window.index)
    primary_error: BaseException | None = None
    try:
        _run_interval_ffmpeg(
            executable,
            source_path=source,
            segment_path=segment_path,
            start_seconds=window.actual_start_seconds,
            duration_seconds=(
                window.actual_end_seconds - window.actual_start_seconds
            ),
        )
        _require_nonempty_interval(segment_path)
        yield segment_path
    except BaseException as error:
        primary_error = error
        raise
    finally:
        _delete_interval_path(segment_path, primary_error=primary_error)


def _validate_interval_window(window: LongAudioIntervalWindow) -> None:
    if type(window) is not LongAudioIntervalWindow:
        raise TypeError("window must be an exact LongAudioIntervalWindow") from None
    if type(window.index) is not int or window.index < 0:
        raise ValueError("window index must be a non-negative integer") from None

    boundaries = (
        window.logical_start_seconds,
        window.logical_end_seconds,
        window.actual_start_seconds,
        window.actual_end_seconds,
    )
    if any(
        type(boundary) not in (int, float) or not math.isfinite(float(boundary))
        for boundary in boundaries
    ):
        raise ValueError("window boundaries must be finite numbers") from None
    if not (
        0.0 <= window.actual_start_seconds
        <= window.logical_start_seconds
        < window.logical_end_seconds
        <= window.actual_end_seconds
    ):
        raise ValueError("window boundaries are inconsistent") from None


def _create_interval_path(parent: Path, *, index: int) -> Path:
    try:
        descriptor, raw_path = tempfile.mkstemp(
            prefix=f".ocrllm-long-audio-interval-{index:06d}-",
            suffix=".mp3",
            dir=parent,
        )
    except (OSError, ValueError) as error:
        raise OutputError(
            "A temporary long-audio interval could not be created.",
            code="OUTPUT_WRITE_FAILED",
        ) from error
    try:
        os.close(descriptor)
    except OSError as error:
        try:
            os.unlink(raw_path)
        except OSError:
            pass
        raise OutputError(
            "A temporary long-audio interval could not be closed.",
            code="OUTPUT_WRITE_FAILED",
        ) from error
    return Path(raw_path)


def _run_interval_ffmpeg(
    executable: Path,
    *,
    source_path: Path,
    segment_path: Path,
    start_seconds: float,
    duration_seconds: float,
) -> None:
    command = [
        os.fspath(executable),
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostats",
        "-y",
        "-ss",
        f"{start_seconds:.6f}",
        "-i",
        os.fspath(source_path),
        "-t",
        f"{duration_seconds:.6f}",
        "-map",
        "0:a:0",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "64k",
        "-c:a",
        "libmp3lame",
        "-map_metadata",
        "-1",
        os.fspath(segment_path),
    ]
    timeout_seconds = max(
        _MINIMUM_FFMPEG_TIMEOUT_SECONDS,
        math.ceil(duration_seconds) + _FFMPEG_TIMEOUT_PADDING_SECONDS,
    )
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=timeout_seconds,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as error:
        raise OutputError(
            "The long-audio interval exceeded its materialization time limit.",
            code="OUTPUT_WRITE_FAILED",
            details={"stage": "interval_materialization"},
        ) from error
    except (OSError, ValueError) as error:
        raise DependencyMissing(
            "The long-audio interval backend could not be executed.",
            details={"extra": "audio"},
        ) from error
    if completed.returncode != 0:
        raise InvalidSource(
            "The owned MP3 interval could not be decoded.",
            code="SOURCE_INVALID",
            details={"stage": "interval_materialization"},
        ) from None


def _require_nonempty_interval(segment_path: Path) -> None:
    try:
        segment_stat = segment_path.stat()
    except (OSError, ValueError) as error:
        raise OutputError(
            "The temporary long-audio interval could not be inspected.",
            code="OUTPUT_WRITE_FAILED",
        ) from error
    if not stat.S_ISREG(segment_stat.st_mode) or segment_stat.st_size <= 0:
        raise OutputError(
            "The temporary long-audio interval is empty or invalid.",
            code="OUTPUT_WRITE_FAILED",
        ) from None


def _delete_interval_path(
    segment_path: Path,
    *,
    primary_error: BaseException | None,
) -> None:
    try:
        segment_path.unlink(missing_ok=True)
    except (OSError, ValueError) as error:
        if primary_error is None:
            raise OutputError(
                "The temporary long-audio interval could not be removed.",
                code="OUTPUT_WRITE_FAILED",
            ) from error
        if isinstance(primary_error, OCRLLMError):
            primary_error._add_safe_detail("interval_cleanup_failed", True)
