"""Own atomic updates to one video resume journal."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .audio.long_audio_partial_state import LongAudioPartialState
from .image_resume_state import ImageResumeState
from .save_video_job_state_atomically import save_video_job_state_atomically
from .video_job_state import VideoAudioState, VideoJobState


class VideoJobJournal:
    """Persist immutable video state after every settled unit."""

    def __init__(self, path: Path, state: VideoJobState) -> None:
        if not isinstance(path, Path):
            raise TypeError("video journal path must be a pathlib.Path") from None
        if type(state) is not VideoJobState:
            raise TypeError("video journal state must be exact VideoJobState") from None
        self._path = path
        self._state = state

    @property
    def state(self) -> VideoJobState:
        """Return the latest durably saved state."""
        return self._state

    @property
    def path(self) -> Path:
        """Return the one fixed journal path owned by this job."""
        return self._path

    def save_initial(self) -> None:
        """Persist the complete provider-free plan before dispatch."""
        save_video_job_state_atomically(self._path, self._state)

    def persist_image_state(self, group_index: int, state: ImageResumeState) -> None:
        """Replace one frame group's partial or completed image state."""
        if type(group_index) is not int or not 0 <= group_index < len(
            self._state.frame_groups
        ):
            raise IndexError("video frame-group index is invalid") from None
        groups = list(self._state.frame_groups)
        groups[group_index] = replace(groups[group_index], image_state=state)
        self._replace(replace(self._state, frame_groups=tuple(groups)))

    def persist_audio(self, audio: VideoAudioState) -> None:
        """Replace audio preparation or settlement state."""
        self._replace(replace(self._state, audio=audio))

    def persist_long_audio_state(self, state: LongAudioPartialState) -> None:
        """Embed one whole/interval paid prefix in the video journal."""
        self.persist_audio(replace(self._state.audio, long_state=state))

    def persist_final_digest(self, digest: str) -> None:
        """Save expected final Markdown identity before publication."""
        self._replace(replace(self._state, final_markdown_sha256=digest))

    def _replace(self, state: VideoJobState) -> None:
        save_video_job_state_atomically(self._path, state)
        self._state = state
