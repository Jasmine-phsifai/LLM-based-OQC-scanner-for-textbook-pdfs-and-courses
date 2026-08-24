"""Inspect one local MP4 without dispatching recognition."""

from __future__ import annotations

import math
import os
import stat
from pathlib import Path

from ..errors import OCRLLMError, InvalidSource, UnsupportedFormat, VideoError
from ..video_info import VideoInfo
from .load_opencv import load_opencv


def inspect_video(source: str | Path) -> VideoInfo:
    """Return validated metadata after decoding the first frame of one MP4."""
    source_path = Path(source)
    _validate_mp4_source(source_path)
    cv2 = load_opencv()

    try:
        capture = cv2.VideoCapture(os.fspath(source_path))
    except Exception as error:
        raise VideoError(
            "The video backend could not open the source.",
            code="VIDEO_INVALID",
        ) from error

    primary_error: BaseException | None = None
    try:
        if not capture.isOpened():
            raise VideoError(
                "The video is malformed or uses an unsupported codec.",
                code="VIDEO_INVALID",
            ) from None

        frames_per_second = _positive_finite_property(
            capture.get(cv2.CAP_PROP_FPS),
            name="frames_per_second",
        )
        frame_count_value = _positive_finite_property(
            capture.get(cv2.CAP_PROP_FRAME_COUNT),
            name="frame_count",
        )
        width_value = _positive_finite_property(
            capture.get(cv2.CAP_PROP_FRAME_WIDTH),
            name="width_pixels",
        )
        height_value = _positive_finite_property(
            capture.get(cv2.CAP_PROP_FRAME_HEIGHT),
            name="height_pixels",
        )
        frame_count = int(frame_count_value)
        width_pixels = int(width_value)
        height_pixels = int(height_value)
        if frame_count <= 0 or width_pixels <= 0 or height_pixels <= 0:
            raise VideoError("The video metadata is invalid.", code="VIDEO_INVALID") from None

        decoded, first_frame = capture.read()
        if not decoded or first_frame is None or getattr(first_frame, "size", 0) <= 0:
            raise VideoError(
                "The video contains no decodable frame.",
                code="VIDEO_INVALID",
            ) from None
        shape = getattr(first_frame, "shape", ())
        if (
            not isinstance(shape, tuple)
            or len(shape) < 2
            or int(shape[0]) != height_pixels
            or int(shape[1]) != width_pixels
        ):
            raise VideoError(
                "The decoded video dimensions do not match its metadata.",
                code="VIDEO_INVALID",
            ) from None

        return VideoInfo(
            frame_count=frame_count,
            frames_per_second=float(frames_per_second),
            duration_seconds=float(frame_count / frames_per_second),
            width_pixels=width_pixels,
            height_pixels=height_pixels,
        )
    except VideoError as error:
        primary_error = error
        raise
    except (KeyboardInterrupt, SystemExit) as error:
        primary_error = error
        raise
    except Exception as error:
        public_error = VideoError(
            "The video backend could not inspect the source.",
            code="VIDEO_INVALID",
        )
        primary_error = public_error
        raise public_error from error
    finally:
        try:
            capture.release()
        except Exception:
            if primary_error is None:
                raise VideoError(
                    "The video backend could not release the source safely.",
                    code="VIDEO_INVALID",
                ) from None
            if isinstance(primary_error, OCRLLMError):
                primary_error._add_safe_detail("video_cleanup_failed", True)


def _validate_mp4_source(source_path: Path) -> None:
    suffix = source_path.suffix.casefold()
    if suffix != ".mp4":
        raise UnsupportedFormat(
            "Video inspection currently accepts exactly one MP4 source.",
            details={"extension": suffix or None},
        ) from None
    try:
        source_stat = source_path.stat()
    except FileNotFoundError as error:
        raise InvalidSource(
            "The video source does not exist.",
            code="SOURCE_NOT_FOUND",
        ) from error
    except (OSError, ValueError) as error:
        raise InvalidSource(
            "The video source cannot be inspected.",
            code="SOURCE_UNREADABLE",
        ) from error
    if not stat.S_ISREG(source_stat.st_mode) or source_stat.st_size <= 0:
        raise InvalidSource(
            "The video source must be a nonempty regular file.",
            code="SOURCE_INVALID",
        ) from None


def _positive_finite_property(value: object, *, name: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or float(value) <= 0
    ):
        raise VideoError(
            "The video metadata is invalid.",
            code="VIDEO_INVALID",
            details={"field": name},
        ) from None
    return float(value)
