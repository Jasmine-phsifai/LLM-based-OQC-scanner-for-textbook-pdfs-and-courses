"""Fully decode one owned short-MP3 snapshot before provider dispatch."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..errors import InvalidSource
from .load_miniaudio import load_miniaudio


MAX_SHORT_MP3_DURATION_SECONDS = 300.0
_STREAM_FRAMES_PER_READ = 4096


def probe_short_mp3(snapshot_path: Path) -> float:
    """Return decoded seconds for one immutable MP3 snapshot.

    The caller owns source snapshotting and provider-envelope limits. This
    function owns MP3-specific metadata validation, bounded-memory full decode,
    and the Stage A1 five-minute decoded-duration limit.
    """

    backend = load_miniaudio()
    try:
        info = backend.mp3_get_file_info(str(snapshot_path))
        channel_count = _positive_integer(info.nchannels)
        sample_rate_hz = _positive_integer(info.sample_rate)
        reported_frame_count = _positive_integer(info.num_frames)

        decoded_sample_count = 0
        stream = backend.mp3_stream_file(
            str(snapshot_path),
            frames_to_read=_STREAM_FRAMES_PER_READ,
        )
        try:
            for samples in stream:
                sample_count = len(samples)
                if sample_count <= 0 or sample_count % channel_count:
                    raise InvalidSource(
                        "The MP3 decoder returned an invalid sample chunk.",
                        code="SOURCE_INVALID",
                    ) from None
                decoded_sample_count += sample_count
        finally:
            stream.close()
    except InvalidSource:
        raise
    except MemoryError:
        raise InvalidSource(
            "The MP3 source could not be decoded within safe memory limits.",
            code="SOURCE_TOO_LARGE",
        ) from None
    except Exception:
        raise InvalidSource(
            "The MP3 source is malformed or could not be decoded completely.",
            code="SOURCE_INVALID",
        ) from None

    decoded_frame_count = decoded_sample_count // channel_count
    if decoded_frame_count <= 0:
        raise InvalidSource(
            "The MP3 source contains no decodable audio frames.",
            code="SOURCE_INVALID",
        ) from None
    if decoded_frame_count != reported_frame_count:
        raise InvalidSource(
            "The MP3 source metadata does not match its decoded audio.",
            code="SOURCE_INVALID",
            details={
                "reported_frame_count": reported_frame_count,
                "decoded_frame_count": decoded_frame_count,
            },
        ) from None

    decoded_duration_seconds = decoded_frame_count / sample_rate_hz
    if decoded_duration_seconds > MAX_SHORT_MP3_DURATION_SECONDS:
        raise InvalidSource(
            "The MP3 source exceeds the five-minute duration limit.",
            code="SOURCE_TOO_LARGE",
            details={
                "decoded_duration_seconds": decoded_duration_seconds,
                "maximum_duration_seconds": MAX_SHORT_MP3_DURATION_SECONDS,
            },
        ) from None
    return decoded_duration_seconds


def _positive_integer(value: Any) -> int:
    if type(value) is not int or value <= 0:
        raise InvalidSource(
            "The MP3 source has invalid audio metadata.",
            code="SOURCE_INVALID",
        ) from None
    return value
