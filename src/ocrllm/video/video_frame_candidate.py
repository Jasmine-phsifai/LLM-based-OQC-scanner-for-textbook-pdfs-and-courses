"""Internal thumbnail metadata used by video frame selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class VideoFrameCandidate:
    """One sampled source position with detail and color thumbnails."""

    frame_index: int
    timestamp_seconds: float
    luminance_thumbnail: Any
    color_thumbnail: Any
