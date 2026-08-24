"""Sample bounded comparison thumbnails from one video."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..errors import VideoError
from ..video_info import VideoInfo
from .open_video_capture import open_video_capture
from .video_frame_candidate import VideoFrameCandidate


_COARSE_INTERVAL_SECONDS = 5.0
_THUMBNAIL_SIZE = (128, 128)
_MAX_CANDIDATES = 10_000


def scan_video_frame_candidates(
    source: Path,
    *,
    video_info: VideoInfo,
    cv2: Any,
) -> tuple[VideoFrameCandidate, ...]:
    """Return ordered five-second thumbnails without retaining full frames."""
    frame_step = max(
        1,
        int(video_info.frames_per_second * _COARSE_INTERVAL_SECONDS),
    )
    candidate_count = (video_info.frame_count + frame_step - 1) // frame_step
    if candidate_count > _MAX_CANDIDATES:
        raise VideoError(
            "The video requires too many comparison samples.",
            code="VIDEO_INVALID",
            details={"maximum_candidate_count": _MAX_CANDIDATES},
        ) from None

    candidates: list[VideoFrameCandidate] = []
    with open_video_capture(source, cv2=cv2) as capture:
        for frame_index in range(0, video_info.frame_count, frame_step):
            try:
                positioned = capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                decoded, frame = capture.read()
                if not positioned or not decoded or frame is None:
                    raise VideoError(
                        "The video backend could not decode a comparison frame.",
                        code="VIDEO_INVALID",
                        details={"frame_index": frame_index},
                    ) from None
                grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                thumbnail = cv2.resize(grayscale, _THUMBNAIL_SIZE)
            except VideoError:
                raise
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as error:
                raise VideoError(
                    "The video backend could not prepare a comparison frame.",
                    code="VIDEO_INVALID",
                    details={"frame_index": frame_index},
                ) from error
            candidates.append(
                VideoFrameCandidate(
                    frame_index=frame_index,
                    timestamp_seconds=frame_index / video_info.frames_per_second,
                    thumbnail=thumbnail,
                )
            )

    if not candidates:
        raise VideoError(
            "The video contains no selectable frame.",
            code="VIDEO_INVALID",
        ) from None
    return tuple(candidates)
