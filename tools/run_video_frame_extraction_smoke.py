"""Prove provider-free full-frame extraction on one explicit real MP4."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import stat
import time
from pathlib import Path

from ocrllm import OCRLLMError, RetainedVideoFrame, extract_video_frames, inspect_video


def parse_arguments() -> argparse.Namespace:
    """Require one explicit source and one new caller-owned output directory."""
    parser = argparse.ArgumentParser(
        description="Prove public video inspection and representative-frame extraction."
    )
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def run_video_frame_extraction_smoke(
    source: Path,
    *,
    output_dir: Path,
) -> dict[str, object]:
    """Return content-free evidence while leaving caller-owned frames in place."""
    source = source.absolute()
    output_dir = output_dir.absolute()
    before = _source_identity(source)
    if os.path.lexists(output_dir):
        return {
            "status": "failed",
            "code": "OUTPUT_NOT_CLEAN",
            "source_unchanged": _source_unchanged(source, before),
            "output_exists": True,
        }
    before_sha256 = _source_sha256(source)

    started = time.monotonic()
    try:
        info = inspect_video(source)
        retained = extract_video_frames(source, output_dir=output_dir)
        valid, output_bytes = _validate_retained_frames(
            retained,
            output_dir=output_dir,
            width_pixels=info.width_pixels,
            height_pixels=info.height_pixels,
        )
    except OCRLLMError as error:
        return _failure_summary(error, source, before, before_sha256, output_dir)
    except Exception:
        return {
            "status": "failed",
            "code": "INVALID_SCENARIO_EVIDENCE",
            "source_unchanged": _source_unchanged(source, before, before_sha256),
            "output_exists": os.path.lexists(output_dir),
            "staging_residue_count": _staging_residue_count(output_dir),
        }

    indexes = tuple(frame.frame_index for frame in retained)
    timestamps = tuple(frame.timestamp_seconds for frame in retained)
    source_unchanged = _source_unchanged(source, before, before_sha256)
    residue_count = _staging_residue_count(output_dir)
    duration_hours = info.duration_seconds / 3600.0
    comparison_sample_upper_bound = (
        math.ceil(
            min(
                info.duration_seconds,
                info.frame_count / info.frames_per_second,
            )
            / 5.0
        )
        + 1
    )
    passed = (
        valid
        and source_unchanged
        and residue_count == 0
        and bool(retained)
        and indexes == tuple(sorted(set(indexes)))
        and timestamps == tuple(sorted(set(timestamps)))
        and 0 <= indexes[0] <= indexes[-1] < info.frame_count
        and 0.0 <= timestamps[0] <= timestamps[-1] <= info.duration_seconds
        and comparison_sample_upper_bound <= 10_000
    )
    return {
        "status": "passed" if passed else "failed",
        "code": None if passed else "INVALID_SCENARIO_EVIDENCE",
        "source_bytes": before[2],
        "source_sha256": before_sha256,
        "source_unchanged": source_unchanged,
        "frame_count": info.frame_count,
        "frames_per_second": info.frames_per_second,
        "duration_seconds": info.duration_seconds,
        "width_pixels": info.width_pixels,
        "height_pixels": info.height_pixels,
        "comparison_sample_upper_bound": comparison_sample_upper_bound,
        "retained_frame_count": len(retained),
        "retained_frames_per_hour": (
            len(retained) / duration_hours if duration_hours > 0.0 else None
        ),
        "first_retained_frame_index": indexes[0],
        "last_retained_frame_index": indexes[-1],
        "first_retained_timestamp_seconds": timestamps[0],
        "last_retained_timestamp_seconds": timestamps[-1],
        "retained_output_bytes": output_bytes,
        "full_frame_dimensions": valid,
        "staging_residue_count": residue_count,
        "elapsed_seconds": time.monotonic() - started,
    }


def _validate_retained_frames(
    retained: object,
    *,
    output_dir: Path,
    width_pixels: int,
    height_pixels: int,
) -> tuple[bool, int]:
    if type(retained) is not tuple or not retained:
        return False, 0

    import cv2
    import numpy as np

    total_bytes = 0
    for frame in retained:
        if type(frame) is not RetainedVideoFrame:
            return False, total_bytes
        expected_name = f"frame-{frame.frame_index:08d}.jpg"
        path = frame.path
        if (
            path.name != expected_name
            or path.parent.name != "frames"
            or path.parent.parent.parent != output_dir
            or path.is_symlink()
        ):
            return False, total_bytes
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size <= 0:
            return False, total_bytes
        encoded = np.frombuffer(path.read_bytes(), dtype=np.uint8)
        decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if (
            decoded is None
            or decoded.shape[1] != width_pixels
            or decoded.shape[0] != height_pixels
        ):
            return False, total_bytes
        total_bytes += info.st_size
    return True, total_bytes


def _failure_summary(
    error: OCRLLMError,
    source: Path,
    before: tuple[int, int, int, int, int],
    before_sha256: str,
    output_dir: Path,
) -> dict[str, object]:
    return {
        "status": "failed",
        "code": error.code,
        "source_unchanged": _source_unchanged(source, before, before_sha256),
        "output_exists": os.path.lexists(output_dir),
        "staging_residue_count": _staging_residue_count(output_dir),
        "video_snapshot_cleanup_failed": (
            error.details.get("video_snapshot_cleanup_failed") is True
        ),
        "video_output_cleanup_failed": (
            error.details.get("video_output_cleanup_failed") is True
        ),
    }


def _source_identity(source: Path) -> tuple[int, int, int, int, int]:
    info = source.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size <= 0:
        raise ValueError("the scenario source must be a nonempty regular file")
    return (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _source_unchanged(
    source: Path,
    before: tuple[int, int, int, int, int],
    before_sha256: str | None = None,
) -> bool:
    try:
        return _source_identity(source) == before and (
            before_sha256 is None or _source_sha256(source) == before_sha256
        )
    except (OSError, ValueError):
        return False


def _source_sha256(source: Path) -> str:
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _staging_residue_count(output_dir: Path) -> int | None:
    try:
        if not output_dir.exists():
            return 0
        return len(tuple(output_dir.rglob(".ocrllm-video-*")))
    except (OSError, ValueError):
        return None


def main() -> int:
    arguments = parse_arguments()
    try:
        summary = run_video_frame_extraction_smoke(
            arguments.source,
            output_dir=arguments.output_dir,
        )
    except Exception:
        summary = {"status": "failed", "code": "INVALID_SCENARIO_EVIDENCE"}
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    return 0 if summary.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
