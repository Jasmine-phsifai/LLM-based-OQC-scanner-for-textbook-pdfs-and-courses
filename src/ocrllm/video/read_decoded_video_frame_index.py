"""Read the index of the frame most recently decoded by OpenCV."""

from __future__ import annotations

import math
from typing import Any

from ..errors import VideoError


def read_decoded_video_frame_index(capture: Any, *, cv2: Any) -> int:
    """Return the decoded index from OpenCV's next-frame cursor."""
    try:
        next_frame_position = capture.get(cv2.CAP_PROP_POS_FRAMES)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        raise VideoError(
            "The decoded video-frame position is invalid.",
            code="VIDEO_INVALID",
        ) from error
    if (
        not isinstance(next_frame_position, (int, float))
        or isinstance(next_frame_position, bool)
        or not math.isfinite(float(next_frame_position))
    ):
        raise VideoError(
            "The decoded video-frame position is invalid.",
            code="VIDEO_INVALID",
        ) from None
    return int(round(float(next_frame_position))) - 1
