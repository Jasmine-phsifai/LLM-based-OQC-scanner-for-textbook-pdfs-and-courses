"""Build the immutable frame-group plan for one video job."""

from __future__ import annotations

from .config import Config
from .fingerprint_image_request import fingerprint_image_request
from .fingerprint_image_sources import fingerprint_image_sources
from .group_retained_video_frames import (
    VIDEO_FRAME_GROUP_LIMIT,
    group_retained_video_frames,
)
from .imaging.snapshot_image_group import snapshot_image_group
from .profiles.resolve_image_profile import resolve_image_profile
from .resolve_effective_image_limit import resolve_effective_image_limit
from .retained_video_frame import RetainedVideoFrame
from .video_job_state import VideoFrameGroupState


def plan_video_frame_groups(
    frames: tuple[RetainedVideoFrame, ...],
    *,
    config: Config,
) -> tuple[VideoFrameGroupState, ...]:
    """Fingerprint every complete retained-frame request before dispatch."""
    profile = resolve_image_profile(config.profile)
    configured_limit, _ = resolve_effective_image_limit(config)
    groups = group_retained_video_frames(
        frames,
        min(VIDEO_FRAME_GROUP_LIMIT, configured_limit),
    )
    planned = []
    for index, group in enumerate(groups):
        source_paths = tuple(frame.path for frame in group)
        with snapshot_image_group(source_paths, config=config) as snapshots:
            identity = fingerprint_image_request(
                fingerprint_image_sources(source_paths, snapshots),
                profile=profile,
                config=config,
            )
        planned.append(
            VideoFrameGroupState(
                index=index,
                frame_indices=tuple(frame.frame_index for frame in group),
                frame_timestamps_seconds=tuple(
                    frame.timestamp_seconds for frame in group
                ),
                identity=identity,
            )
        )
    return tuple(planned)
