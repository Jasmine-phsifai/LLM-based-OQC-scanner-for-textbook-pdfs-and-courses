"""Prepare retained frames from one stable request-owned video."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ..errors import OutputError, OutputExists
from ..output.claim_output_target import claim_output_target
from ..output.normalize_output_stem import normalize_output_stem
from ..retained_video_frame import RetainedVideoFrame
from .coerce_video_output_directory import coerce_video_output_directory
from .inspect_video import inspect_video
from .load_opencv import load_opencv
from .scan_video_frame_candidates import scan_video_frame_candidates
from .select_video_frame_candidates import select_video_frame_candidates
from .snapshot_video_source import snapshot_video_source
from .write_selected_video_frames import write_selected_video_frames


@contextmanager
def prepare_video_media(
    source: str | Path,
    *,
    output_dir: str | Path,
) -> Iterator[tuple[Path, tuple[RetainedVideoFrame, ...]]]:
    """Yield one stable MP4 path and its published representative JPEGs."""
    output_directory = coerce_video_output_directory(output_dir)
    source_path = Path(source)
    target_root = output_directory / normalize_output_stem(source_path.stem)
    _preflight_video_output(target_root)

    with claim_output_target(target_root):
        _preflight_video_output(target_root)
        with snapshot_video_source(
            source_path,
            snapshot_parent=target_root.parent,
        ) as snapshot_path:
            video_info = inspect_video(snapshot_path)
            cv2 = load_opencv()
            candidates = scan_video_frame_candidates(
                snapshot_path,
                video_info=video_info,
                cv2=cv2,
            )
            selected = select_video_frame_candidates(
                candidates,
                duration_seconds=video_info.duration_seconds,
                cv2=cv2,
            )
            retained_frames = write_selected_video_frames(
                snapshot_path,
                selected,
                target_root=target_root,
                cv2=cv2,
            )
            yield snapshot_path, retained_frames


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
