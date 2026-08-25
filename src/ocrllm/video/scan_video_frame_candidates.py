"""Sample bounded comparison thumbnails from one video."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from ..errors import VideoError
from ..video_info import VideoInfo
from .open_video_capture import open_video_capture
from .video_frame_candidate import VideoFrameCandidate


_COARSE_INTERVAL_SECONDS = 5.0
_THUMBNAIL_SIZE = (128, 128)
_COLOR_THUMBNAIL_SIZE = (32, 32)
_MAX_CANDIDATES = 10_000


def scan_video_frame_candidates(
    source: Path,
    *,
    video_info: VideoInfo,
    cv2: Any,
) -> tuple[VideoFrameCandidate, ...]:
    """Return ordered five-second thumbnails without retaining full frames."""
    visual_duration_estimate = min(
        video_info.duration_seconds,
        video_info.frame_count / video_info.frames_per_second,
    )
    coarse_sample_count = math.ceil(
        visual_duration_estimate / _COARSE_INTERVAL_SECONDS
    )
    final_frame_index = video_info.frame_count - 1
    candidate_count = coarse_sample_count + 1
    if candidate_count > _MAX_CANDIDATES:
        raise VideoError(
            "The video requires too many comparison samples.",
            code="VIDEO_INVALID",
            details={"maximum_candidate_count": _MAX_CANDIDATES},
        ) from None

    candidates: list[VideoFrameCandidate] = []
    with open_video_capture(source, cv2=cv2) as capture:
        for sample_index in range(coarse_sample_count):
            candidate = _read_candidate(
                capture,
                position_property=cv2.CAP_PROP_POS_MSEC,
                position_value=(
                    sample_index * _COARSE_INTERVAL_SECONDS * 1000.0
                ),
                expected_frame_index=None,
                video_info=video_info,
                cv2=cv2,
            )
            _append_ordered_candidate(candidates, candidate)

        if not candidates or candidates[-1].frame_index != final_frame_index:
            _append_ordered_candidate(
                candidates,
                _read_candidate(
                    capture,
                    position_property=cv2.CAP_PROP_POS_FRAMES,
                    position_value=final_frame_index,
                    expected_frame_index=final_frame_index,
                    video_info=video_info,
                    cv2=cv2,
                ),
            )

    if not candidates:
        raise VideoError(
            "The video contains no selectable frame.",
            code="VIDEO_INVALID",
        ) from None
    return tuple(candidates)


def _append_ordered_candidate(
    candidates: list[VideoFrameCandidate],
    candidate: VideoFrameCandidate,
) -> None:
    if candidates and (
        candidate.frame_index < candidates[-1].frame_index
        or candidate.timestamp_seconds < candidates[-1].timestamp_seconds
    ):
        raise VideoError(
            "The decoded comparison frames are not in source order.",
            code="VIDEO_INVALID",
        ) from None
    if not candidates or candidate.frame_index != candidates[-1].frame_index:
        candidates.append(candidate)


def _read_candidate(
    capture: Any,
    *,
    position_property: int,
    position_value: float,
    expected_frame_index: int | None,
    video_info: VideoInfo,
    cv2: Any,
) -> VideoFrameCandidate:
    try:
        positioned = capture.set(position_property, position_value)
        decoded, frame = capture.read()
        next_frame_position = capture.get(cv2.CAP_PROP_POS_FRAMES)
        timestamp_milliseconds = capture.get(cv2.CAP_PROP_POS_MSEC)
        if not positioned or not decoded or frame is None:
            raise VideoError(
                "The video backend could not decode a comparison frame.",
                code="VIDEO_INVALID",
            ) from None
        if (
            not isinstance(next_frame_position, (int, float))
            or isinstance(next_frame_position, bool)
            or not math.isfinite(float(next_frame_position))
        ):
            raise VideoError(
                "The decoded video-frame position is invalid.",
                code="VIDEO_INVALID",
            ) from None
        frame_index = int(round(float(next_frame_position))) - 1
        if not 0 <= frame_index < video_info.frame_count:
            raise VideoError(
                "The decoded video-frame position is invalid.",
                code="VIDEO_INVALID",
                details={"frame_index": frame_index},
            ) from None
        if expected_frame_index is not None and frame_index != expected_frame_index:
            raise VideoError(
                "The video backend decoded a different comparison frame.",
                code="VIDEO_INVALID",
                details={"frame_index": expected_frame_index},
            ) from None
        if (
            not isinstance(timestamp_milliseconds, (int, float))
            or isinstance(timestamp_milliseconds, bool)
            or not math.isfinite(float(timestamp_milliseconds))
            or float(timestamp_milliseconds) < 0
        ):
            raise VideoError(
                "The decoded video-frame timestamp is invalid.",
                code="VIDEO_INVALID",
                details={"frame_index": frame_index},
            ) from None
        grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        luminance_thumbnail = cv2.resize(grayscale, _THUMBNAIL_SIZE)
        color_thumbnail = cv2.resize(frame, _COLOR_THUMBNAIL_SIZE)
    except VideoError:
        raise
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        raise VideoError(
            "The video backend could not prepare a comparison frame.",
            code="VIDEO_INVALID",
        ) from error
    return VideoFrameCandidate(
        frame_index=frame_index,
        timestamp_seconds=float(timestamp_milliseconds) / 1000.0,
        luminance_thumbnail=luminance_thumbnail,
        color_thumbnail=color_thumbnail,
    )
