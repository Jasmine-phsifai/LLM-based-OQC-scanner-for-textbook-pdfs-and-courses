"""Decide whether saved video audio can finish without a credential."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .video_job_state import VideoAudioState


def video_audio_requires_credential_preflight(audio: VideoAudioState) -> bool:
    """Return whether resume must preflight a credential before new work."""
    if audio.state == "pending":
        return True
    if audio.state == "absent":
        return False
    if audio.mode == "short":
        return audio.short_state is None
    long_state = audio.long_state
    return long_state is None or len(long_state.slots) < len(
        long_state.request_fingerprints
    )
