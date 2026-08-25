"""Choose one existing Google adapter for one video-owned MP3 snapshot."""

from __future__ import annotations

from pathlib import Path

from ..audio.probe_short_mp3 import MAX_SHORT_MP3_DURATION_SECONDS
from ..audio.snapshot_long_mp3 import LongMP3Snapshot
from ..audio.snapshot_short_mp3 import ShortMP3Snapshot
from ..audio.snapshot_video_mp3 import snapshot_video_mp3
from ..audio.transcription_prompt import AUDIO_TRANSCRIPTION_PROMPT
from ..config import Config
from ..errors import OutputError
from ..processor_output import ProcessorOutput
from ..providers.google_genai.recognize_short_mp3 import recognize_short_mp3
from ..providers.google_genai.recognize_uploaded_mp3 import recognize_uploaded_mp3
from ..raise_if_cancelled import raise_if_cancelled
from .build_long_mp3_processor_output import build_long_mp3_processor_output
from .build_short_mp3_processor_output import build_short_mp3_processor_output


def recognize_video_mp3(source_path: Path, *, config: Config) -> ProcessorOutput:
    """Decode once, select one route, and keep the recognition in memory."""
    raise_if_cancelled(config.cancellation)
    processor_output: ProcessorOutput | None = None
    try:
        with snapshot_video_mp3(source_path, temp_dir=config.temp_dir) as snapshot:
            if snapshot.duration_seconds <= MAX_SHORT_MP3_DURATION_SECONDS:
                short_snapshot = ShortMP3Snapshot(
                    path=snapshot.path,
                    byte_size=snapshot.byte_size,
                    sha256=snapshot.sha256,
                    duration_seconds=snapshot.duration_seconds,
                )
                response = recognize_short_mp3(
                    short_snapshot,
                    prompt=AUDIO_TRANSCRIPTION_PROMPT,
                    config=config,
                )
                processor_output = build_short_mp3_processor_output(
                    short_snapshot,
                    response,
                    config=config,
                )
            else:
                long_snapshot = LongMP3Snapshot(
                    path=snapshot.path,
                    byte_size=snapshot.byte_size,
                    sha256=snapshot.sha256,
                    duration_seconds=snapshot.duration_seconds,
                )
                response = recognize_uploaded_mp3(
                    long_snapshot,
                    prompt=AUDIO_TRANSCRIPTION_PROMPT,
                    config=config,
                )
                processor_output = build_long_mp3_processor_output(
                    long_snapshot,
                    response,
                    config=config,
                )
    except OutputError as error:
        if processor_output is not None:
            error._add_safe_detail("provider_calls_attempted", 1)
            metadata = processor_output.metadata
            if metadata.get("remote_file_deleted") is False:
                error._add_safe_detail("provider_file_cleanup_failed", True)
            if metadata.get("provider_client_closed") is False:
                error._add_safe_detail("provider_client_cleanup_failed", True)
        raise
    assert processor_output is not None
    return processor_output
