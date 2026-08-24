"""Extract one validated MP3 audio artifact from a local MP4."""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
from pathlib import Path

from ..errors import OCRLLMError, OutputError, OutputExists, VideoError
from ..output.claim_output_target import claim_output_target
from .inspect_video import inspect_video
from .load_imageio_ffmpeg import load_imageio_ffmpeg_executable


_FFMPEG_TIMEOUT_SECONDS = 600


def extract_video_audio(
    source: str | Path,
    *,
    output_path: str | Path,
) -> Path:
    """Atomically publish one mono 16 kHz MP3 without recognizing it."""
    source_path = Path(source)
    target = Path(output_path)
    _preflight_audio_output(target)

    with claim_output_target(target):
        _preflight_audio_output(target)
        inspect_video(source_path)
        ffmpeg = load_imageio_ffmpeg_executable()
        _require_video_audio_stream(source_path, ffmpeg=ffmpeg)
        staging_path = _create_staging_path(target.parent)
        primary_error: BaseException | None = None
        try:
            _run_ffmpeg(
                ffmpeg,
                (
                    "-i",
                    os.fspath(source_path),
                    "-map",
                    "0:a:0",
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-c:a",
                    "libmp3lame",
                    "-b:a",
                    "32k",
                    "-map_metadata",
                    "-1",
                    "-write_xing",
                    "1",
                    os.fspath(staging_path),
                ),
                stage="extraction",
            )
            _validate_staged_mp3(staging_path, ffmpeg=ffmpeg)
            _preflight_audio_output(target)
            _publish_staged_mp3(staging_path, target)
            return target
        except BaseException as error:
            primary_error = error
            raise
        finally:
            _delete_staging_path(staging_path, primary_error=primary_error)


def _preflight_audio_output(output_path: Path) -> None:
    if output_path.suffix.casefold() != ".mp3":
        raise OutputError(
            "The extracted video audio output must use the .mp3 extension.",
            code="OUTPUT_PATH_INVALID",
        ) from None
    try:
        parent_stat = os.lstat(output_path.parent)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        is_reparse_point = bool(
            getattr(parent_stat, "st_file_attributes", 0) & reparse_flag
        )
        if not stat.S_ISDIR(parent_stat.st_mode) or is_reparse_point:
            raise OutputError(
                "The extracted audio output parent must be a plain directory.",
                code="OUTPUT_PATH_INVALID",
            ) from None
        if os.path.lexists(output_path):
            raise OutputExists("The requested extracted audio output already exists.")
    except (OutputError, OutputExists):
        raise
    except (OSError, ValueError) as error:
        raise OutputError(
            "The extracted audio output path could not be inspected.",
            code="OUTPUT_PATH_INVALID",
        ) from error


def _create_staging_path(output_parent: Path) -> Path:
    try:
        descriptor, raw_path = tempfile.mkstemp(
            prefix=".ocrllm-audio-",
            suffix=".mp3",
            dir=output_parent,
        )
    except (OSError, ValueError) as error:
        raise OutputError(
            "A temporary extracted-audio file could not be created.",
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
            "A temporary extracted-audio file could not be closed.",
            code="OUTPUT_WRITE_FAILED",
        ) from error
    return Path(raw_path)


def _run_ffmpeg(
    executable: Path,
    arguments: tuple[str, ...],
    *,
    stage: str,
) -> None:
    returncode = _run_ffmpeg_returncode(
        executable,
        arguments,
        stage=stage,
    )
    if returncode != 0:
        raise VideoError(
            "The video audio stream is invalid or could not be decoded.",
            code="VIDEO_INVALID",
            details={"stage": stage},
        ) from None


def _run_ffmpeg_returncode(
    executable: Path,
    arguments: tuple[str, ...],
    *,
    stage: str,
) -> int:
    try:
        completed = subprocess.run(
            [
                os.fspath(executable),
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostats",
                "-y",
                *arguments,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=_FFMPEG_TIMEOUT_SECONDS,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as error:
        raise VideoError(
            "Video audio processing exceeded its bounded execution time.",
            code="VIDEO_INVALID",
            details={"stage": stage},
        ) from error
    except (OSError, ValueError) as error:
        raise VideoError(
            "The video audio backend could not be executed.",
            code="VIDEO_BACKEND_UNAVAILABLE",
            details={"stage": stage},
        ) from error
    return completed.returncode


def _require_video_audio_stream(source_path: Path, *, ffmpeg: Path) -> None:
    required_arguments = (
        "-xerror",
        "-i",
        os.fspath(source_path),
        "-map",
        "0:a:0",
        "-frames:a",
        "1",
        "-c:a",
        "copy",
        "-f",
        "null",
        "-",
    )
    if (
        _run_ffmpeg_returncode(
            ffmpeg,
            required_arguments,
            stage="audio_stream_probe",
        )
        == 0
    ):
        return

    optional_arguments = tuple(
        "0:a:0?" if argument == "0:a:0" else argument
        for argument in required_arguments
    )
    if (
        _run_ffmpeg_returncode(
            ffmpeg,
            optional_arguments,
            stage="audio_stream_probe",
        )
        == 0
    ):
        raise VideoError(
            "The video has no audio stream.",
            code="VIDEO_NO_AUDIO_STREAM",
            details={"stage": "audio_stream_probe"},
        ) from None
    raise VideoError(
        "The video audio stream could not be inspected.",
        code="VIDEO_INVALID",
        details={"stage": "audio_stream_probe"},
    ) from None


def _validate_staged_mp3(staging_path: Path, *, ffmpeg: Path) -> None:
    try:
        staging_stat = staging_path.stat()
    except (OSError, ValueError) as error:
        raise VideoError(
            "The extracted video audio could not be inspected.",
            code="VIDEO_INVALID",
        ) from error
    if not stat.S_ISREG(staging_stat.st_mode) or staging_stat.st_size <= 0:
        raise VideoError(
            "The extracted video audio is empty or invalid.",
            code="VIDEO_INVALID",
        ) from None
    _run_ffmpeg(
        ffmpeg,
        (
            "-xerror",
            "-i",
            os.fspath(staging_path),
            "-map",
            "0:a:0",
            "-f",
            "null",
            "-",
        ),
        stage="validation",
    )


def _publish_staged_mp3(staging_path: Path, output_path: Path) -> None:
    try:
        with staging_path.open("r+b") as stream:
            os.fsync(stream.fileno())
        os.replace(staging_path, output_path)
    except (OSError, ValueError) as error:
        raise OutputError(
            "The extracted video audio could not be published.",
            code="OUTPUT_WRITE_FAILED",
        ) from error


def _delete_staging_path(
    staging_path: Path,
    *,
    primary_error: BaseException | None,
) -> None:
    try:
        staging_path.unlink(missing_ok=True)
    except (OSError, ValueError) as error:
        if primary_error is None:
            raise OutputError(
                "The temporary extracted-audio file could not be removed.",
                code="OUTPUT_WRITE_FAILED",
            ) from error
        if isinstance(primary_error, OCRLLMError):
            primary_error._add_safe_detail("audio_cleanup_failed", True)
