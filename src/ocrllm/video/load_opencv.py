"""Load the optional OpenCV video backend lazily."""

from __future__ import annotations

from typing import Any

from ..errors import DependencyMissing, VideoError


def load_opencv() -> Any:
    """Return OpenCV or raise one typed optional-dependency failure."""
    try:
        import cv2
    except (ImportError, OSError) as error:
        raise DependencyMissing(
            "Video inspection requires the optional 'video' extra.",
            details={"extra": "video"},
        ) from error

    required_names = (
        "CAP_PROP_FPS",
        "CAP_PROP_FRAME_COUNT",
        "CAP_PROP_FRAME_WIDTH",
        "CAP_PROP_FRAME_HEIGHT",
        "CAP_PROP_POS_FRAMES",
        "CAP_PROP_POS_MSEC",
        "VideoCapture",
    )
    if any(not hasattr(cv2, name) for name in required_names):
        raise VideoError(
            "The installed video backend does not expose the required API.",
            code="VIDEO_BACKEND_UNAVAILABLE",
            details={"extra": "video"},
        ) from None
    return cv2
