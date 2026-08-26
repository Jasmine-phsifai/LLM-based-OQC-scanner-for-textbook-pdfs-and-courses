"""Publish selected video frames as one complete directory."""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..errors import OCRLLMError, OutputError, OutputExists, VideoError
from ..retained_video_frame import RetainedVideoFrame
from .open_video_capture import open_video_capture
from .read_decoded_video_frame_index import read_decoded_video_frame_index
from .video_frame_candidate import VideoFrameCandidate


def write_selected_video_frames(
    source: Path,
    candidates: tuple[VideoFrameCandidate, ...],
    *,
    target_root: Path,
    cv2: Any,
) -> tuple[RetainedVideoFrame, ...]:
    """Publish validated JPEGs only after every selected frame is written."""
    staging_root = target_root.parent / f".ocrllm-video-{uuid4().hex}.tmp"
    primary_error: BaseException | None = None
    published = False
    try:
        _prepare_staging_root(staging_root, target_root=target_root)
        staging_frames = staging_root / "frames"
        staging_frames.mkdir()
        with open_video_capture(source, cv2=cv2) as capture:
            for candidate in candidates:
                _write_one_selected_frame(
                    capture,
                    candidate,
                    staging_frames=staging_frames,
                    cv2=cv2,
                )
        if os.path.lexists(target_root):
            raise OutputExists("The requested video output directory already exists.")
        try:
            os.rename(staging_root, target_root)
        except FileExistsError as error:
            raise OutputExists(
                "The requested video output directory already exists."
            ) from error
        except (OSError, ValueError) as error:
            if os.path.lexists(target_root):
                raise OutputExists(
                    "The requested video output directory already exists."
                ) from error
            raise OutputError(
                "The retained video-frame directory could not be published.",
                code="OUTPUT_WRITE_FAILED",
            ) from error
        published = True
        final_frames = target_root / "frames"
        return tuple(
            RetainedVideoFrame(
                frame_index=candidate.frame_index,
                timestamp_seconds=candidate.timestamp_seconds,
                path=final_frames / _frame_filename(candidate.frame_index),
            )
            for candidate in candidates
        )
    except BaseException as error:
        primary_error = error
        raise
    finally:
        if not published and os.path.lexists(staging_root):
            try:
                shutil.rmtree(staging_root)
            except (OSError, ValueError):
                if primary_error is None:
                    raise OutputError(
                        "The temporary video-frame directory could not be removed.",
                        code="OUTPUT_WRITE_FAILED",
                    ) from None
                if isinstance(primary_error, OCRLLMError):
                    primary_error._add_safe_detail("video_output_cleanup_failed", True)


def _prepare_staging_root(staging_root: Path, *, target_root: Path) -> None:
    try:
        target_root.parent.mkdir(parents=True, exist_ok=True)
        if not target_root.parent.is_dir():
            raise OutputError(
                "The video output parent is not a directory.",
                code="OUTPUT_PATH_INVALID",
            ) from None
        if os.path.lexists(target_root):
            raise OutputExists("The requested video output directory already exists.")
        staging_root.mkdir()
    except (OutputError, OutputExists):
        raise
    except (OSError, ValueError) as error:
        raise OutputError(
            "The video output directory could not be created.",
            code="OUTPUT_PATH_INVALID",
        ) from error


def _write_one_selected_frame(
    capture: Any,
    candidate: VideoFrameCandidate,
    *,
    staging_frames: Path,
    cv2: Any,
) -> None:
    try:
        positioned = capture.set(cv2.CAP_PROP_POS_FRAMES, candidate.frame_index)
        decoded, frame = capture.read()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        raise VideoError(
            "The selected video frame could not be decoded.",
            code="VIDEO_INVALID",
            details={"frame_index": candidate.frame_index},
        ) from error
    if not positioned or not decoded or frame is None:
        raise VideoError(
            "The selected video frame could not be decoded.",
            code="VIDEO_INVALID",
            details={"frame_index": candidate.frame_index},
        ) from None
    decoded_frame_index = read_decoded_video_frame_index(capture, cv2=cv2)
    if decoded_frame_index != candidate.frame_index:
        raise VideoError(
            "The video backend decoded a different selected frame.",
            code="VIDEO_INVALID",
            details={"frame_index": candidate.frame_index},
        ) from None

    output_path = staging_frames / _frame_filename(candidate.frame_index)
    try:
        # OpenCV filename I/O can reject non-ASCII paths on Windows. Keep
        # OpenCV responsible for JPEG bytes and let Python own path handling.
        encoded, jpeg = cv2.imencode(".jpg", frame)
        if not encoded:
            raise OutputError(
                "A retained video frame was not written completely.",
                code="OUTPUT_WRITE_FAILED",
                details={"frame_index": candidate.frame_index},
            ) from None
        with output_path.open("xb") as output_file:
            written_bytes = output_file.write(memoryview(jpeg))
        output_stat = output_path.stat()
        verified = cv2.imdecode(jpeg, cv2.IMREAD_COLOR)
        if (
            written_bytes != jpeg.nbytes
            or not stat.S_ISREG(output_stat.st_mode)
            or output_stat.st_size != jpeg.nbytes
            or verified is None
            or getattr(verified, "shape", None) != getattr(frame, "shape", None)
        ):
            raise OutputError(
                "A retained video frame was not written completely.",
                code="OUTPUT_WRITE_FAILED",
                details={"frame_index": candidate.frame_index},
            ) from None
    except OutputError:
        raise
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        raise OutputError(
            "A retained video frame could not be written.",
            code="OUTPUT_WRITE_FAILED",
            details={"frame_index": candidate.frame_index},
        ) from error


def _frame_filename(frame_index: int) -> str:
    return f"frame-{frame_index:08d}.jpg"
