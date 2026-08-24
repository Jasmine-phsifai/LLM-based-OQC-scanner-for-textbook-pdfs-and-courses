"""Inspect one local MP4 without dispatching recognition."""

from __future__ import annotations

import math
import stat
from pathlib import Path

from ..errors import InvalidSource, UnsupportedFormat, VideoError
from ..video_info import VideoInfo
from .load_opencv import load_opencv
from .open_video_capture import open_video_capture


def inspect_video(source: str | Path) -> VideoInfo:
    """Return validated metadata after decoding the first frame of one MP4."""
    source_path = Path(source)
    _validate_mp4_source(source_path)
    cv2 = load_opencv()

    with open_video_capture(source_path, cv2=cv2) as capture:
        try:
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
                raise VideoError(
                    "The video metadata is invalid.",
                    code="VIDEO_INVALID",
                ) from None

            decoded, first_frame = capture.read()
            if (
                not decoded
                or first_frame is None
                or getattr(first_frame, "size", 0) <= 0
            ):
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
        except VideoError:
            raise
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as error:
            raise VideoError(
                "The video backend could not inspect the source.",
                code="VIDEO_INVALID",
            ) from error


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
