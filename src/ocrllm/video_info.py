"""Immutable metadata returned by video inspection."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VideoInfo:
    """Validated metadata for one locally decodable video."""

    frame_count: int
    frames_per_second: float
    duration_seconds: float
    width_pixels: int
    height_pixels: int

    def __post_init__(self) -> None:
        if type(self.frame_count) is not int or self.frame_count <= 0:
            raise ValueError("VideoInfo.frame_count must be a positive integer")
        if (
            not isinstance(self.frames_per_second, (int, float))
            or isinstance(self.frames_per_second, bool)
            or not math.isfinite(float(self.frames_per_second))
            or float(self.frames_per_second) <= 0
        ):
            raise ValueError("VideoInfo.frames_per_second must be finite and positive")
        if (
            not isinstance(self.duration_seconds, (int, float))
            or isinstance(self.duration_seconds, bool)
            or not math.isfinite(float(self.duration_seconds))
            or float(self.duration_seconds) <= 0
        ):
            raise ValueError("VideoInfo.duration_seconds must be finite and positive")
        if type(self.width_pixels) is not int or self.width_pixels <= 0:
            raise ValueError("VideoInfo.width_pixels must be a positive integer")
        if type(self.height_pixels) is not int or self.height_pixels <= 0:
            raise ValueError("VideoInfo.height_pixels must be a positive integer")
        object.__setattr__(self, "frames_per_second", float(self.frames_per_second))
        object.__setattr__(self, "duration_seconds", float(self.duration_seconds))
