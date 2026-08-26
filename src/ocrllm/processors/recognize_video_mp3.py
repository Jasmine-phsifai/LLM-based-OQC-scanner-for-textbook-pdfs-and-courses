"""Choose one existing Google adapter for one video-owned MP3 snapshot."""

from __future__ import annotations

from pathlib import Path

from ..audio.probe_short_mp3 import MAX_SHORT_MP3_DURATION_SECONDS
from ..audio.remove_long_audio_temporary_state import (
    remove_long_audio_temporary_state,
)
from ..audio.snapshot_long_mp3 import LongMP3Snapshot
from ..audio.snapshot_short_mp3 import ShortMP3Snapshot
from ..audio.snapshot_video_mp3 import snapshot_video_mp3
from ..audio.transcription_prompt import AUDIO_TRANSCRIPTION_PROMPT
from ..config import Config
from ..errors import OutputError
from ..processor_output import ProcessorOutput
from ..providers.google_genai.recognize_short_mp3 import recognize_short_mp3
from ..raise_if_cancelled import raise_if_cancelled
from .build_short_mp3_processor_output import build_short_mp3_processor_output
from .recognize_long_mp3_intervals import recognize_long_mp3_intervals
from .recognize_long_mp3_whole import recognize_long_mp3_whole


def recognize_video_mp3(
    source_path: Path,
    *,
    config: Config,
    interval_minutes: int | None,
    state_path: Path,
) -> ProcessorOutput:
    """Decode once, select one route, and keep the recognition in memory."""
    raise_if_cancelled(config.cancellation)
    processor_output: ProcessorOutput | None = None
    long_audio_settled = False
    try:
        snapshot_context = (
            snapshot_video_mp3(
                source_path,
                temp_dir=config.temp_dir,
                interval_mode=True,
            )
            if interval_minutes is not None
            else snapshot_video_mp3(source_path, temp_dir=config.temp_dir)
        )
        with snapshot_context as snapshot:
            if (
                snapshot.duration_seconds <= MAX_SHORT_MP3_DURATION_SECONDS
                and interval_minutes is None
            ):
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
                if interval_minutes is None:
                    processor_output, _ = recognize_long_mp3_whole(
                        long_snapshot,
                        config=config,
                        state_path=state_path,
                        saved_state=None,
                    )
                else:
                    processor_output, _ = recognize_long_mp3_intervals(
                        long_snapshot,
                        config=config,
                        interval_minutes=interval_minutes,
                        state_path=state_path,
                        saved_state=None,
                    )
                long_audio_settled = True
    except OutputError as error:
        if processor_output is not None:
            metadata = processor_output.metadata
            current_calls = metadata.get("current_run_provider_call_count")
            if type(current_calls) is not int or current_calls < 0:
                current_calls = 1
            error._add_safe_detail("provider_calls_attempted", current_calls)
            if metadata.get("remote_file_deleted") is False:
                error._add_safe_detail("provider_file_cleanup_failed", True)
            if metadata.get("provider_client_closed") is False:
                error._add_safe_detail("provider_client_cleanup_failed", True)
        raise
    assert processor_output is not None
    if long_audio_settled:
        return remove_long_audio_temporary_state(state_path, processor_output)
    return processor_output
