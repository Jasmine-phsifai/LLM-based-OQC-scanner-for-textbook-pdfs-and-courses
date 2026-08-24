"""Extract selected JPEG frames from one local MP4."""

from __future__ import annotations

import os
from pathlib import Path

from ..errors import OutputError, OutputExists
from ..output.claim_output_target import claim_output_target
from ..output.normalize_output_stem import normalize_output_stem
from ..retained_video_frame import RetainedVideoFrame
from .inspect_video import inspect_video
from .load_opencv import load_opencv
from .scan_video_frame_candidates import scan_video_frame_candidates
from .select_video_frame_candidates import select_video_frame_candidates
from .write_selected_video_frames import write_selected_video_frames


def extract_video_frames(
    source: str | Path,
    *,
    output_dir: str | Path,
) -> tuple[RetainedVideoFrame, ...]:
    """Retain ordered representative JPEGs without provider dispatch."""
    source_path = Path(source)
    output_parent = Path(output_dir)
    target_root = output_parent / normalize_output_stem(source_path.stem)
    _preflight_video_output(target_root)

    with claim_output_target(target_root):
        _preflight_video_output(target_root)
        video_info = inspect_video(source_path)
        cv2 = load_opencv()
        candidates = scan_video_frame_candidates(
            source_path,
            video_info=video_info,
            cv2=cv2,
        )
        selected = select_video_frame_candidates(
            candidates,
            duration_seconds=video_info.duration_seconds,
            cv2=cv2,
        )
        return write_selected_video_frames(
            source_path,
            selected,
            target_root=target_root,
            cv2=cv2,
        )


def _preflight_video_output(target_root: Path) -> None:
    try:
        if target_root.parent.exists() and not target_root.parent.is_dir():
            raise OutputError(
                "The video output parent must be a directory.",
                code="OUTPUT_PATH_INVALID",
            ) from None
        if os.path.lexists(target_root):
            raise OutputExists("The requested video output directory already exists.")
    except (OutputError, OutputExists):
        raise
    except (OSError, ValueError) as error:
        raise OutputError(
            "The video output path could not be inspected.",
            code="OUTPUT_PATH_INVALID",
        ) from error

