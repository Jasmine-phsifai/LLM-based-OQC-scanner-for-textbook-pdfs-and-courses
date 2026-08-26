"""Immutable state for one resumable video-to-Markdown job."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping

from .audio.long_audio_partial_state import LongAudioPartialState
from .contracts.source_fingerprint import SourceFingerprint
from .freeze_json_value import JSONValue, freeze_json_value
from .image_request_identity import ImageRequestIdentity
from .image_resume_state import ImageResumeState


VIDEO_JOB_STATE_VERSION = "ocrllm.video-job.v1"
VIDEO_JOB_STATE_NAME = ".ocrllm-video-resume.json"
VIDEO_JOB_RESULT_NAME = "result.md"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True, kw_only=True)
class VideoFrameGroupState:
    """Bind one ordered retained-frame group to optional recognized state."""

    index: int
    frame_indices: tuple[int, ...]
    frame_timestamps_seconds: tuple[float, ...]
    identity: ImageRequestIdentity
    image_state: ImageResumeState | None = None

    def __post_init__(self) -> None:
        if type(self.index) is not int or self.index < 0:
            raise ValueError("video frame-group index is invalid") from None
        if (
            type(self.frame_indices) is not tuple
            or not self.frame_indices
            or any(type(value) is not int or value < 0 for value in self.frame_indices)
        ):
            raise ValueError("video frame-group indices are invalid") from None
        if (
            type(self.frame_timestamps_seconds) is not tuple
            or len(self.frame_timestamps_seconds) != len(self.frame_indices)
            or any(
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or float(value) < 0
                or not math.isfinite(float(value))
                for value in self.frame_timestamps_seconds
            )
        ):
            raise ValueError("video frame-group timestamps are invalid") from None
        if type(self.identity) is not ImageRequestIdentity:
            raise TypeError("video frame-group identity is invalid") from None
        if (
            _SHA256.fullmatch(self.identity.request_fingerprint) is None
            or type(self.identity.identity_version) is not str
            or not self.identity.identity_version
            or type(self.identity.processor_name) is not str
            or not self.identity.processor_name
            or type(self.identity.processor_version) is not str
            or not self.identity.processor_version
            or type(self.identity.sources) is not tuple
            or any(
                type(source) is not SourceFingerprint or source.byte_size <= 0
                for source in self.identity.sources
            )
        ):
            raise ValueError("video frame-group request identity is invalid") from None
        if len(self.identity.sources) != len(self.frame_indices):
            raise ValueError("video frame-group identity is not aligned") from None
        if self.image_state is not None:
            if type(self.image_state) is not ImageResumeState:
                raise TypeError("video frame-group image state is invalid") from None
            if (
                self.image_state.identity_version != self.identity.identity_version
                or self.image_state.request_fingerprint
                != self.identity.request_fingerprint
                or self.image_state.processor_name != self.identity.processor_name
                or self.image_state.processor_version != self.identity.processor_version
                or self.image_state.sources != self.identity.sources
            ):
                raise ValueError("video frame-group image state does not match its plan")
        object.__setattr__(
            self,
            "frame_timestamps_seconds",
            tuple(float(value) for value in self.frame_timestamps_seconds),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class VideoShortAudioState:
    """Store one settled short-audio result or terminal no-speech fact."""

    request_fingerprint: str
    markdown: str | None
    markdown_sha256: str | None
    status: Literal["complete", "partial"]
    warnings: tuple[str, ...]
    metadata: Mapping[str, JSONValue] = field(default_factory=dict)
    no_speech: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.request_fingerprint) is not str
            or _SHA256.fullmatch(self.request_fingerprint) is None
        ):
            raise ValueError("short-audio request fingerprint is invalid") from None
        if type(self.no_speech) is not bool:
            raise TypeError("short-audio no_speech must be a boolean") from None
        if self.no_speech:
            if self.markdown is not None or self.markdown_sha256 is not None:
                raise ValueError("no-speech state cannot contain Markdown") from None
        else:
            if type(self.markdown) is not str or not self.markdown.strip():
                raise ValueError("short-audio state Markdown is invalid") from None
            if (
                type(self.markdown_sha256) is not str
                or _SHA256.fullmatch(self.markdown_sha256) is None
                or self.markdown_sha256
                != hashlib.sha256(self.markdown.encode("utf-8")).hexdigest()
            ):
                raise ValueError("short-audio state Markdown digest is invalid") from None
        if self.status not in {"complete", "partial"}:
            raise ValueError("short-audio state status is invalid") from None
        if type(self.warnings) is not tuple or any(
            type(warning) is not str or not warning.strip() for warning in self.warnings
        ):
            raise ValueError("short-audio state warnings are invalid") from None
        frozen = freeze_json_value(self.metadata)
        if not isinstance(frozen, MappingProxyType):
            raise ValueError("short-audio state metadata is invalid") from None
        object.__setattr__(self, "metadata", frozen)


@dataclass(frozen=True, slots=True, kw_only=True)
class VideoAudioState:
    """Describe audio preparation and optional settled recognition state."""

    state: Literal["pending", "absent", "ready"]
    mode: Literal["short", "whole", "interval"] | None
    interval_minutes: int | None
    model: str
    artifact: SourceFingerprint | None = None
    duration_seconds: float | None = None
    short_state: VideoShortAudioState | None = None
    long_state: LongAudioPartialState | None = None

    def __post_init__(self) -> None:
        if self.state not in {"pending", "absent", "ready"}:
            raise ValueError("video audio state is invalid") from None
        if type(self.model) is not str or not self.model.strip():
            raise ValueError("video audio model is invalid") from None
        if self.state in {"pending", "absent"}:
            if any(
                value is not None
                for value in (
                    self.mode,
                    self.artifact,
                    self.duration_seconds,
                    self.short_state,
                    self.long_state,
                )
            ):
                raise ValueError("unprepared video audio carries settled facts") from None
            if self.interval_minutes is not None and (
                type(self.interval_minutes) is not int or self.interval_minutes <= 0
            ):
                raise ValueError("video audio interval is invalid") from None
            return
        if self.mode not in {"short", "whole", "interval"}:
            raise ValueError("ready video audio mode is invalid") from None
        if type(self.artifact) is not SourceFingerprint:
            raise TypeError("ready video audio artifact is invalid") from None
        if self.artifact.byte_size <= 0:
            raise ValueError("ready video audio artifact is empty") from None
        if (
            not isinstance(self.duration_seconds, (int, float))
            or isinstance(self.duration_seconds, bool)
            or float(self.duration_seconds) <= 0
            or not math.isfinite(float(self.duration_seconds))
        ):
            raise ValueError("ready video audio duration is invalid") from None
        object.__setattr__(self, "duration_seconds", float(self.duration_seconds))
        if self.mode == "interval":
            if type(self.interval_minutes) is not int or self.interval_minutes <= 0:
                raise ValueError("interval video audio has no valid minutes") from None
        elif self.interval_minutes is not None:
            raise ValueError("non-interval video audio cannot carry minutes") from None
        if self.mode == "short":
            if self.long_state is not None:
                raise ValueError("short video audio cannot carry long state") from None
        else:
            if self.short_state is not None:
                raise ValueError("long video audio cannot carry short state") from None
            if self.long_state is not None:
                expected_mode = "interval" if self.mode == "interval" else "whole"
                if (
                    self.long_state.mode != expected_mode
                    or self.long_state.interval_minutes != self.interval_minutes
                ):
                    raise ValueError("long video audio state does not match its mode")


@dataclass(frozen=True, slots=True, kw_only=True)
class VideoJobState:
    """Keep every fact required to resume one fixed-result video job."""

    state_version: str
    source: SourceFingerprint
    frame_groups: tuple[VideoFrameGroupState, ...]
    audio: VideoAudioState
    final_markdown_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.state_version != VIDEO_JOB_STATE_VERSION:
            raise ValueError("video job state version is unsupported") from None
        if type(self.source) is not SourceFingerprint:
            raise TypeError("video job source identity is invalid") from None
        if self.source.byte_size <= 0:
            raise ValueError("video job source identity is empty") from None
        if (
            type(self.frame_groups) is not tuple
            or not self.frame_groups
            or any(type(group) is not VideoFrameGroupState for group in self.frame_groups)
            or tuple(group.index for group in self.frame_groups)
            != tuple(range(len(self.frame_groups)))
        ):
            raise ValueError("video job frame groups are invalid") from None
        flattened = tuple(
            frame_index
            for group in self.frame_groups
            for frame_index in group.frame_indices
        )
        if any(current <= previous for previous, current in zip(flattened, flattened[1:])):
            raise ValueError("video job frame indices are not strictly ordered") from None
        timestamps = tuple(
            timestamp
            for group in self.frame_groups
            for timestamp in group.frame_timestamps_seconds
        )
        if any(current < previous for previous, current in zip(timestamps, timestamps[1:])):
            raise ValueError("video job frame timestamps are not ordered") from None
        if type(self.audio) is not VideoAudioState:
            raise TypeError("video job audio state is invalid") from None
        if self.final_markdown_sha256 is not None and (
            type(self.final_markdown_sha256) is not str
            or _SHA256.fullmatch(self.final_markdown_sha256) is None
        ):
            raise ValueError("video job final Markdown digest is invalid") from None
        if self.final_markdown_sha256 is not None and not _is_fully_settled(self):
            raise ValueError("video job final Markdown identity precedes settlement")


def _is_fully_settled(state: VideoJobState) -> bool:
    if any(
        group.image_state is None or not group.image_state.markdown
        for group in state.frame_groups
    ):
        return False
    audio = state.audio
    if audio.state == "absent":
        return True
    if audio.state != "ready":
        return False
    if audio.mode == "short":
        return audio.short_state is not None
    return (
        audio.long_state is not None
        and len(audio.long_state.slots)
        == len(audio.long_state.request_fingerprints)
    )
