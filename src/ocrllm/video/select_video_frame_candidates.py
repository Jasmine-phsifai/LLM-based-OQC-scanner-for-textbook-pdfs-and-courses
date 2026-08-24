"""Select video candidates with bounded negative feedback."""

from __future__ import annotations

from typing import Any

from .video_frame_candidate import VideoFrameCandidate


_CHANGE_THRESHOLD = 0.15
_DRIFT_THRESHOLD = 0.10
_MAX_SEGMENT_SECONDS = 150.0
_TARGET_LOW_PER_HOUR = 28.0
_TARGET_HIGH_PER_HOUR = 40.0
_MAX_FEEDBACK_ATTEMPTS = 10


def select_video_frame_candidates(
    candidates: tuple[VideoFrameCandidate, ...],
    *,
    duration_seconds: float,
    cv2: Any,
) -> tuple[VideoFrameCandidate, ...]:
    """Adjust segmentation sensitivity from observed retained-frame density."""
    if len(candidates) <= 1:
        return candidates

    duration_hours = duration_seconds / 3600.0
    target_low = max(5, int(duration_hours * _TARGET_LOW_PER_HOUR + 0.5))
    target_high = max(10, int(duration_hours * _TARGET_HIGH_PER_HOUR + 0.5))
    target_midpoint = (target_low + target_high) / 2.0
    low_sensitivity = 0.2
    high_sensitivity = 4.0
    best = candidates
    best_distance = float("inf")

    for _ in range(_MAX_FEEDBACK_ATTEMPTS):
        sensitivity = (low_sensitivity + high_sensitivity) / 2.0
        selected = _segment_video_frame_candidates(
            candidates,
            change_threshold=_CHANGE_THRESHOLD * sensitivity,
            drift_threshold=_DRIFT_THRESHOLD * sensitivity,
            max_segment_seconds=_MAX_SEGMENT_SECONDS * sensitivity,
            cv2=cv2,
        )
        distance = abs(len(selected) - target_midpoint)
        if distance < best_distance:
            best = selected
            best_distance = distance
        if target_low <= len(selected) <= target_high:
            return selected
        if len(selected) < target_low:
            high_sensitivity = sensitivity
        else:
            low_sensitivity = sensitivity

    if len(best) <= target_high:
        return best
    step = len(best) / target_high
    return tuple(best[int(index * step)] for index in range(target_high))


def _segment_video_frame_candidates(
    candidates: tuple[VideoFrameCandidate, ...],
    *,
    change_threshold: float,
    drift_threshold: float,
    max_segment_seconds: float,
    cv2: Any,
) -> tuple[VideoFrameCandidate, ...]:
    segments: list[tuple[int, int]] = []
    segment_start = 0
    for index in range(1, len(candidates)):
        adjacent_change = _thumbnail_difference(
            candidates[index - 1].thumbnail,
            candidates[index].thumbnail,
            cv2=cv2,
        )
        accumulated_drift = _thumbnail_difference(
            candidates[segment_start].thumbnail,
            candidates[index].thumbnail,
            cv2=cv2,
        )
        if adjacent_change > change_threshold or accumulated_drift > drift_threshold:
            segments.append((segment_start, index - 1))
            segment_start = index
    segments.append((segment_start, len(candidates) - 1))

    bounded_segments: list[tuple[int, int]] = []
    for start, end in segments:
        duration = (
            candidates[end].timestamp_seconds
            - candidates[start].timestamp_seconds
        )
        if duration <= max_segment_seconds:
            bounded_segments.append((start, end))
            continue
        part_count = max(2, int(duration / max_segment_seconds + 0.5))
        part_duration = duration / part_count
        part_start = start
        for part_index in range(1, part_count):
            cut_time = candidates[start].timestamp_seconds + part_duration * part_index
            part_end = part_start
            for candidate_index in range(part_start, end + 1):
                if candidates[candidate_index].timestamp_seconds <= cut_time:
                    part_end = candidate_index
                else:
                    break
            if part_end > part_start:
                bounded_segments.append((part_start, part_end))
                part_start = part_end + 1
        bounded_segments.append((part_start, end))

    return tuple(candidates[end] for _, end in bounded_segments)


def _thumbnail_difference(first: Any, second: Any, *, cv2: Any) -> float:
    difference = cv2.absdiff(first, second)
    _, changed = cv2.threshold(difference, 25, 255, cv2.THRESH_BINARY)
    return float(cv2.countNonZero(changed)) / float(changed.size)

