"""Immutable metadata for one retained video frame."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RetainedVideoFrame:
    """One selected JPEG with its stable source position."""

    frame_index: int
    timestamp_seconds: float
    path: Path

    def __post_init__(self) -> None:
        if type(self.frame_index) is not int or self.frame_index < 0:
            raise ValueError("RetainedVideoFrame.frame_index must be a nonnegative integer")
        if (
            not isinstance(self.timestamp_seconds, (int, float))
            or isinstance(self.timestamp_seconds, bool)
            or not math.isfinite(float(self.timestamp_seconds))
            or float(self.timestamp_seconds) < 0
        ):
            raise ValueError(
                "RetainedVideoFrame.timestamp_seconds must be finite and nonnegative"
            )
        if not isinstance(self.path, Path):
            raise TypeError("RetainedVideoFrame.path must be a pathlib.Path")
        object.__setattr__(self, "timestamp_seconds", float(self.timestamp_seconds))
