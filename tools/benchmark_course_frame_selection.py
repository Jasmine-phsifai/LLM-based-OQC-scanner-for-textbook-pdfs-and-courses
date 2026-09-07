"""Benchmark OCRLLM's existing video selector on private extracted-frame manifests.

This is an on-demand benchmark bridge, not an OCRLLM public image-package API.
It reuses the current video selector's thumbnail construction and fixed
selection parameters after the caller has already extracted the images.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import time
from collections.abc import Mapping, Sequence
from pathlib import Path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def run_benchmark(manifest_path: Path, output_dir: Path) -> dict[str, object]:
    """Select and copy each private course's frames, returning path-free evidence."""
    manifest_path = manifest_path.absolute()
    output_dir = output_dir.absolute()
    if output_dir.exists() or output_dir.is_symlink():
        raise ValueError("--output-dir must not already exist")
    manifest = _load_manifest(manifest_path)
    lectures = _lectures(manifest)
    output_dir.mkdir(parents=True)
    try:
        import cv2
        import numpy as np
        from ocrllm.video.scan_video_frame_candidates import _THUMBNAIL_SIZE
        from ocrllm.video.scan_video_frame_candidates import _COLOR_THUMBNAIL_SIZE
        from ocrllm.video.select_video_frame_candidates import (
            select_video_frame_candidates,
        )
        from ocrllm.video.video_frame_candidate import VideoFrameCandidate

        reports: list[dict[str, object]] = []
        for lecture in lectures:
            reports.append(
                _process_lecture(
                    lecture,
                    manifest_parent=manifest_path.parent,
                    output_dir=output_dir,
                    cv2=cv2,
                    video_frame_candidate=VideoFrameCandidate,
                    select_candidates=select_video_frame_candidates,
                    numpy=np,
                    thumbnail_size=_THUMBNAIL_SIZE,
                    color_thumbnail_size=_COLOR_THUMBNAIL_SIZE,
                )
            )
        report = {
            "status": "passed",
            "lecture_count": len(reports),
            "lectures": tuple(reports),
        }
    except BaseException:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise
    (output_dir / "selection-report.json").write_text(
        json.dumps(report, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def _process_lecture(
    lecture: Mapping[str, object],
    *,
    manifest_parent: Path,
    output_dir: Path,
    cv2: object,
    numpy: object,
    video_frame_candidate: type,
    select_candidates,
    thumbnail_size: tuple[int, int],
    color_thumbnail_size: tuple[int, int],
) -> dict[str, object]:
    lecture_id = _text(lecture.get("lecture_id"), "lecture_id")
    duration_seconds = _positive_number(lecture.get("duration_seconds"), "duration_seconds")
    raw_frames = lecture.get("frames")
    if type(raw_frames) is not list or not raw_frames:
        raise ValueError(f"{lecture_id}: frames must be a nonempty list")
    records = tuple(_frame_record(item, index) for index, item in enumerate(raw_frames))
    frame_indices = tuple(record[3] for record in records)
    if len(set(frame_indices)) != len(frame_indices):
        raise ValueError(f"{lecture_id}: frame_index values must be unique")
    if tuple(record[2] for record in records) != tuple(sorted(record[2] for record in records)):
        raise ValueError(f"{lecture_id}: frame timestamps must be nondecreasing")

    scan_started = time.monotonic()
    candidates = []
    for path_value, sample_id, timestamp, frame_index in records:
        source_path = Path(path_value)
        if not source_path.is_absolute():
            source_path = manifest_parent / source_path
        encoded = source_path.read_bytes()
        array = cv2.imdecode(numpy.frombuffer(encoded, dtype="uint8"), cv2.IMREAD_COLOR)
        if array is None or getattr(array, "size", 0) <= 0:
            raise ValueError(f"{lecture_id}: image could not be decoded")
        grayscale = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
        candidates.append(
            video_frame_candidate(
                frame_index=frame_index,
                timestamp_seconds=timestamp,
                luminance_thumbnail=cv2.resize(grayscale, thumbnail_size),
                color_thumbnail=cv2.resize(array, color_thumbnail_size),
            )
        )
    scan_seconds = time.monotonic() - scan_started

    select_started = time.monotonic()
    selected = select_candidates(
        tuple(candidates),
        duration_seconds=duration_seconds,
        cv2=cv2,
    )
    select_seconds = time.monotonic() - select_started

    course_output = output_dir / _safe_component(lecture_id) / "frames"
    course_output.mkdir(parents=True)
    copy_started = time.monotonic()
    selected_manifest = []
    by_index = {record[3]: record for record in records}
    for ordinal, candidate in enumerate(selected, start=1):
        source_path = Path(by_index[candidate.frame_index][0])
        if not source_path.is_absolute():
            source_path = manifest_parent / source_path
        destination = course_output / f"frame-{ordinal:04d}-{candidate.frame_index:08d}{source_path.suffix.lower()}"
        shutil.copyfile(source_path, destination)
        selected_manifest.append(
            {
                "sample_id": by_index[candidate.frame_index][1],
                "frame_index": candidate.frame_index,
                "timestamp_seconds": candidate.timestamp_seconds,
                "filename": destination.name,
            }
        )
    copy_seconds = time.monotonic() - copy_started
    (course_output.parent / "selected-manifest.json").write_text(
        json.dumps(
            {
                "lecture_id": lecture_id,
                "duration_seconds": duration_seconds,
                "source_frame_count": len(records),
                "selected_frame_count": len(selected_manifest),
                "frames": selected_manifest,
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "lecture_id": lecture_id,
        "duration_seconds": duration_seconds,
        "source_frame_count": len(records),
        "selected_frame_count": len(selected_manifest),
        "scan_seconds": round(scan_seconds, 6),
        "selection_seconds": round(select_seconds, 6),
        "copy_seconds": round(copy_seconds, 6),
        "selected_timestamps_seconds": tuple(item["timestamp_seconds"] for item in selected_manifest),
    }


def _load_manifest(path: Path) -> Mapping[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("manifest root must be an object")
    return value


def _lectures(manifest: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    value = manifest.get("lectures")
    if type(value) is not list or not value or any(not isinstance(item, Mapping) for item in value):
        raise ValueError("manifest.lectures must be a nonempty list of objects")
    return tuple(value)


def _frame_record(value: object, fallback_index: int) -> tuple[str, str, float, int]:
    if not isinstance(value, Mapping):
        raise ValueError("each frame must be an object")
    path = _text(value.get("path"), "frame.path")
    sample_id = _text(value.get("sample_id", f"frame-{fallback_index}"), "frame.sample_id")
    timestamp = _positive_number(value.get("timestamp_seconds"), "frame.timestamp_seconds", allow_zero=True)
    frame_index = value.get("frame_index", fallback_index)
    if type(frame_index) is not int or frame_index < 0:
        raise ValueError("frame.frame_index must be a nonnegative integer")
    return path, sample_id, timestamp, frame_index


def _safe_component(value: str) -> str:
    """Return a bounded private output-directory component."""
    component = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    if not component:
        raise ValueError("lecture_id has no safe output-directory component")
    return component[:96]


def _text(value: object, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{field} must be nonempty text")
    return value


def _positive_number(value: object, field: str, *, allow_zero: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    number = float(value)
    if number < 0 or (number == 0 and not allow_zero):
        raise ValueError(f"{field} must be positive")
    return number


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_benchmark(args.manifest, args.output_dir)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
