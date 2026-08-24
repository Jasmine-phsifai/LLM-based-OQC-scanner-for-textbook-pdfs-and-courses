"""Own one short-lived OpenCV video capture."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from ..errors import OCRLLMError, VideoError


@contextmanager
def open_video_capture(source: Path, *, cv2: Any) -> Iterator[Any]:
    """Yield one opened capture and always release it without hiding failures."""
    try:
        capture = cv2.VideoCapture(os.fspath(source))
    except Exception as error:
        raise VideoError(
            "The video backend could not open the source.",
            code="VIDEO_INVALID",
        ) from error

    primary_error: BaseException | None = None
    try:
        try:
            opened = capture is not None and capture.isOpened()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as error:
            raise VideoError(
                "The video backend could not open the source.",
                code="VIDEO_INVALID",
            ) from error
        if not opened:
            raise VideoError(
                "The video is malformed or uses an unsupported codec.",
                code="VIDEO_INVALID",
            ) from None
        yield capture
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            if capture is not None:
                capture.release()
        except Exception:
            if primary_error is None:
                raise VideoError(
                    "The video backend could not release the source safely.",
                    code="VIDEO_INVALID",
                ) from None
            if isinstance(primary_error, OCRLLMError):
                primary_error._add_safe_detail("video_cleanup_failed", True)
