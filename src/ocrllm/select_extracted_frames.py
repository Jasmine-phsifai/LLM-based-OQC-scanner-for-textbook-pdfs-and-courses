"""Select existing complete JPEG frames without owning their publication."""
from __future__ import annotations

from .observe_recognition import observed_stage

import math

from .retained_video_frame import RetainedVideoFrame


@observed_stage('select_frames', 'ocr')
def select_extracted_frames(
    frames: tuple[RetainedVideoFrame, ...], *, duration_seconds: float,
) -> tuple[RetainedVideoFrame, ...]:
    """Return an ordered subset using the existing duration-aware video selector.

    The caller supplies source timestamps, then owns copying/archiving returned
    paths. No image is cropped, rewritten, renamed or deleted by this function.
    """
    if type(frames) is not tuple or not frames or any(
        type(frame) is not RetainedVideoFrame for frame in frames
    ):
        raise ValueError("frames must be a nonempty tuple of RetainedVideoFrame")
    if isinstance(duration_seconds, bool) or not isinstance(duration_seconds, (int, float)) or not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError("duration_seconds must be finite and positive")
    if len({frame.frame_index for frame in frames}) != len(frames):
        raise ValueError("frame indices must be unique")
    timestamps = tuple(frame.timestamp_seconds for frame in frames)
    if timestamps != tuple(sorted(timestamps)) or timestamps[-1] > duration_seconds:
        raise ValueError("frame timestamps must be ordered and within duration")

    from .video.load_opencv import load_opencv
    from .video.scan_video_frame_candidates import _THUMBNAIL_SIZE, _COLOR_THUMBNAIL_SIZE
    from .video.select_video_frame_candidates import select_video_frame_candidates
    from .video.video_frame_candidate import VideoFrameCandidate
    from .errors import InvalidSource
    import numpy as np

    cv2 = load_opencv()
    candidates = []
    for frame in frames:
        array = cv2.imdecode(np.frombuffer(frame.path.read_bytes(), dtype="uint8"), cv2.IMREAD_COLOR)
        if array is None or array.size <= 0:
            raise InvalidSource("An extracted frame cannot be decoded.", code="SOURCE_INVALID")
        grayscale = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
        candidates.append(VideoFrameCandidate(
            frame_index=frame.frame_index, timestamp_seconds=frame.timestamp_seconds,
            luminance_thumbnail=cv2.resize(grayscale, _THUMBNAIL_SIZE),
            color_thumbnail=cv2.resize(array, _COLOR_THUMBNAIL_SIZE),
        ))
    selected = select_video_frame_candidates(tuple(candidates), duration_seconds=duration_seconds, cv2=cv2)
    by_index = {frame.frame_index: frame for frame in frames}
    return tuple(by_index[item.frame_index] for item in selected)
