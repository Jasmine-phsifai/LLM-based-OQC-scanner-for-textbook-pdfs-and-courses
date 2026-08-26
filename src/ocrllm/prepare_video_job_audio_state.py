"""Build provider-free audio identity for one video job."""

from __future__ import annotations

from pathlib import Path

from .audio.probe_short_mp3 import MAX_SHORT_MP3_DURATION_SECONDS
from .audio.snapshot_video_mp3 import snapshot_video_mp3
from .build_owned_media_fingerprint import build_owned_media_fingerprint
from .config import Config
from .video_job_state import VideoAudioState


def prepare_video_job_audio_state(
    artifact: Path,
    *,
    config: Config,
    interval_minutes: int | None,
) -> VideoAudioState:
    """Validate one extracted MP3 and bind its selected route before dispatch."""
    snapshot_context = (
        snapshot_video_mp3(
            artifact,
            temp_dir=config.temp_dir,
            interval_mode=True,
        )
        if interval_minutes is not None
        else snapshot_video_mp3(artifact, temp_dir=config.temp_dir)
    )
    with snapshot_context as snapshot:
        mode = (
            "interval"
            if interval_minutes is not None
            else (
                "short"
                if snapshot.duration_seconds <= MAX_SHORT_MP3_DURATION_SECONDS
                else "whole"
            )
        )
        model = config.audio_model.name
        assert type(model) is str
        return VideoAudioState(
            state="ready",
            mode=mode,
            interval_minutes=interval_minutes,
            model=model,
            artifact=build_owned_media_fingerprint(
                artifact,
                byte_size=snapshot.byte_size,
                sha256=snapshot.sha256,
            ),
            duration_seconds=snapshot.duration_seconds,
        )
