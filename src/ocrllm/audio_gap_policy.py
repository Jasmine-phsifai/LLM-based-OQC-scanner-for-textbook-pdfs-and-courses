"""Explicit caller limits for accepting bounded, evidenced audio gaps."""
from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True, kw_only=True)
class AudioGapPolicy:
    """Opt in to at most two repeated output-limit attempts on short leaves.

    No acceptance fraction is supplied by default. Only output_token_limit
    leaves of at most 120 seconds can qualify; other failures stay partial.
    """
    max_failed_fraction: float
    max_failed_segment_seconds: float
    max_failed_seconds: float | None = None

    def __post_init__(self):
        if self.max_failed_fraction is None or self.max_failed_segment_seconds is None:
            raise ValueError('Required audio gap limits must be finite numbers.')
        for value in (self.max_failed_fraction, self.max_failed_segment_seconds, self.max_failed_seconds):
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
                raise ValueError('Audio gap limits must be finite numbers.')
        if not 0 <= self.max_failed_fraction < 1:
            raise ValueError('max_failed_fraction must be in [0, 1).')
        if not 0 < self.max_failed_segment_seconds <= 120:
            raise ValueError('max_failed_segment_seconds must be in (0, 120].')
        if self.max_failed_seconds is not None and self.max_failed_seconds < 0:
            raise ValueError('max_failed_seconds must be nonnegative.')
