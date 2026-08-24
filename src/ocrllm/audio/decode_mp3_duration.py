"""Fully decode one owned MP3 with bounded Python memory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..errors import InvalidSource


STREAM_FRAMES_PER_READ = 4096


def decode_mp3_duration(snapshot_path: Path, *, backend: object) -> float:
    """Return decoded seconds after validating metadata and every sample chunk."""
    try:
        info = backend.mp3_get_file_info(str(snapshot_path))
        channel_count = _positive_integer(info.nchannels)
        sample_rate_hz = _positive_integer(info.sample_rate)
        reported_frame_count = _positive_integer(info.num_frames)

        decoded_sample_count = 0
        stream = backend.mp3_stream_file(
            str(snapshot_path),
            frames_to_read=STREAM_FRAMES_PER_READ,
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
    return decoded_frame_count / sample_rate_hz


def _positive_integer(value: Any) -> int:
    if type(value) is not int or value <= 0:
        raise InvalidSource(
            "The MP3 source has invalid audio metadata.",
            code="SOURCE_INVALID",
        ) from None
    return value
