"""Extract selected JPEG frames from one local MP4."""

from __future__ import annotations

from pathlib import Path

from ..retained_video_frame import RetainedVideoFrame
from .prepare_video_media import prepare_video_media


def extract_video_frames(
    source: str | Path,
    *,
    output_dir: str | Path,
) -> tuple[RetainedVideoFrame, ...]:
    """Retain ordered representative JPEGs without provider dispatch."""
    with prepare_video_media(source, output_dir=output_dir) as (_, retained_frames):
        return retained_frames
