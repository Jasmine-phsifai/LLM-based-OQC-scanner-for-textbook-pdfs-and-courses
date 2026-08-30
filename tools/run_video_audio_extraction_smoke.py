"""Prove provider-free audio extraction and planning on one explicit real MP4."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import stat
import sys
import time
from pathlib import Path

from ocrllm import (
    AudioSlice,
    GOOGLE_GEMINI_2_5_FLASH,
    OCRLLMError,
    extract_video_audio,
    inspect_video,
    split_audio,
)


INTERVAL_MINUTES = 30
INTERVAL_CONTEXT_SECONDS = 30.0
MAX_PRODUCT_AUDIO_SECONDS = 36_000.0


def parse_arguments() -> argparse.Namespace:
    """Require one explicit source and one new caller-owned MP3 target."""
    parser = argparse.ArgumentParser(
        description="Prove public video-audio extraction and range planning."
    )
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def run_video_audio_extraction_smoke(
    source: Path,
    *,
    output: Path,
) -> dict[str, object]:
    """Return content-free evidence while leaving caller-owned audio in place."""
    source = source.absolute()
    output = output.absolute()
    try:
        before = _source_identity(source)
    except (OSError, ValueError):
        return {
            "status": "failed",
            "code": "INVALID_SOURCE_EVIDENCE",
            "output": _artifact_summary(output),
            "staging_residue_count": _staging_residue_count(output.parent),
        }
    if os.path.lexists(output):
        return {
            "status": "failed",
            "code": "OUTPUT_NOT_CLEAN",
            "source_unchanged": _source_unchanged(source, before),
            "output": {"exists": True},
            "staging_residue_count": _staging_residue_count(output.parent),
        }
    try:
        before_sha256 = _sha256(source)
    except OSError:
        return {
            "status": "failed",
            "code": "INVALID_SOURCE_EVIDENCE",
            "source_bytes": before[2],
            "source_unchanged": _source_unchanged(source, before),
            "output": _artifact_summary(output),
            "staging_residue_count": _staging_residue_count(output.parent),
        }
    started = time.monotonic()
    try:
        video_info = inspect_video(source)
        extracted = extract_video_audio(source, output_path=output)
        whole = split_audio(extracted, interval_minutes=-1)
        explicit = split_audio(extracted, interval_minutes=INTERVAL_MINUTES)
        provider_default = split_audio(
            extracted,
            provider=GOOGLE_GEMINI_2_5_FLASH,
        )
    except OCRLLMError as error:
        return _failure_summary(error, source, before, before_sha256, output)
    except Exception:
        return {
            "status": "failed",
            "code": "INVALID_SCENARIO_EVIDENCE",
            "source_unchanged": _source_unchanged(
                source,
                before,
                before_sha256,
            ),
            "source_bytes": before[2],
            "source_sha256": before_sha256,
            "output": _artifact_summary(output),
            "staging_residue_count": _staging_residue_count(output.parent),
        }

    output_info = output.stat()
    audio_duration = _whole_duration(whole, output)
    expected_interval_count = (
        math.ceil(audio_duration / float(INTERVAL_MINUTES * 60))
        if audio_duration is not None
        else None
    )
    explicit_valid = (
        audio_duration is not None
        and _valid_interval_plan(
            explicit,
            source=output,
            duration_seconds=audio_duration,
        )
    )
    provider_default_matches = (
        type(provider_default) is tuple
        and provider_default == explicit
    )
    source_unchanged = _source_unchanged(source, before, before_sha256)
    staging_residue_count = _staging_residue_count(output.parent)
    google_genai_sdk_loaded = _google_genai_sdk_loaded()
    passed = (
        extracted == output
        and stat.S_ISREG(output_info.st_mode)
        and not output.is_symlink()
        and output_info.st_size > 0
        and audio_duration is not None
        and audio_duration <= MAX_PRODUCT_AUDIO_SECONDS
        and explicit_valid
        and provider_default_matches
        and expected_interval_count == len(explicit)
        and source_unchanged
        and staging_residue_count == 0
        and not google_genai_sdk_loaded
    )
    return {
        "status": "passed" if passed else "failed",
        "code": None if passed else "INVALID_SCENARIO_EVIDENCE",
        "source_bytes": before[2],
        "source_sha256": before_sha256,
        "source_unchanged": source_unchanged,
        "video_duration_seconds": video_info.duration_seconds,
        "audio_duration_seconds": audio_duration,
        "duration_delta_seconds": (
            audio_duration - video_info.duration_seconds
            if audio_duration is not None
            else None
        ),
        "output_bytes": output_info.st_size,
        "output_sha256": _sha256(output),
        "whole_slice_count": len(whole),
        "explicit_interval_minutes": INTERVAL_MINUTES,
        "explicit_interval_slice_count": len(explicit),
        "provider_default_minutes": (
            GOOGLE_GEMINI_2_5_FLASH.default_audio_minutes
        ),
        "provider_default_matches_explicit": provider_default_matches,
        "final_logical_end_seconds": (
            explicit[-1].logical_end_seconds if explicit else None
        ),
        "staging_residue_count": staging_residue_count,
        "google_genai_sdk_loaded": google_genai_sdk_loaded,
        "provider_call_count": 0,
        "elapsed_seconds": time.monotonic() - started,
    }


def _whole_duration(
    whole: object,
    source: Path,
) -> float | None:
    if (
        type(whole) is not tuple
        or len(whole) != 1
        or type(whole[0]) is not AudioSlice
    ):
        return None
    item = whole[0]
    if (
        item.source != source
        or item.index != 0
        or item.logical_start_seconds != 0.0
        or item.actual_start_seconds != 0.0
        or item.logical_end_seconds != item.actual_end_seconds
        or item.logical_end_seconds <= 0.0
    ):
        return None
    return item.logical_end_seconds


def _valid_interval_plan(
    plan: object,
    *,
    source: Path,
    duration_seconds: float,
) -> bool:
    if type(plan) is not tuple or not plan:
        return False
    logical_start = 0.0
    interval_seconds = float(INTERVAL_MINUTES * 60)
    for index, item in enumerate(plan):
        logical_end = min(logical_start + interval_seconds, duration_seconds)
        if (
            type(item) is not AudioSlice
            or item.source != source
            or item.index != index
            or item.logical_start_seconds != logical_start
            or item.logical_end_seconds != logical_end
            or item.actual_start_seconds
            != max(0.0, logical_start - INTERVAL_CONTEXT_SECONDS)
            or item.actual_end_seconds
            != min(duration_seconds, logical_end + INTERVAL_CONTEXT_SECONDS)
        ):
            return False
        logical_start = logical_end
    return logical_start == duration_seconds


def _failure_summary(
    error: OCRLLMError,
    source: Path,
    before: tuple[int, int, int, int, int],
    before_sha256: str,
    output: Path,
) -> dict[str, object]:
    return {
        "status": "failed",
        "code": error.code,
        "stage": error.details.get("stage"),
        "source_bytes": before[2],
        "source_sha256": before_sha256,
        "source_unchanged": _source_unchanged(source, before, before_sha256),
        "output": _artifact_summary(output),
        "staging_residue_count": _staging_residue_count(output.parent),
        "audio_cleanup_failed": error.details.get("audio_cleanup_failed") is True,
        "video_snapshot_cleanup_failed": (
            error.details.get("video_snapshot_cleanup_failed") is True
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
            before_sha256 is None or _sha256(source) == before_sha256
        )
    except (OSError, ValueError):
        return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _staging_residue_count(parent: Path) -> int | None:
    try:
        return len(
            tuple(parent.glob(".ocrllm-audio-*"))
            + tuple(parent.glob(".ocrllm-video-source-*"))
        )
    except (OSError, ValueError):
        return None


def _artifact_summary(path: Path) -> dict[str, object]:
    try:
        if not path.is_file() or path.is_symlink():
            return {"exists": os.path.lexists(path)}
        return {
            "exists": True,
            "size": path.stat().st_size,
            "sha256": _sha256(path),
        }
    except (OSError, ValueError):
        return {"exists": os.path.lexists(path), "inspectable": False}


def _google_genai_sdk_loaded() -> bool:
    return any(
        name == "google.genai" or name.startswith("google.genai.")
        for name in sys.modules
    )


def main() -> int:
    arguments = parse_arguments()
    try:
        summary = run_video_audio_extraction_smoke(
            arguments.source,
            output=arguments.output,
        )
    except Exception:
        summary = {"status": "failed", "code": "INVALID_SCENARIO_EVIDENCE"}
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    return 0 if summary.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
