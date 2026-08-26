"""Strictly parse one video job journal."""

from __future__ import annotations

import json

from .audio.parse_long_audio_partial_state_document import (
    parse_long_audio_partial_state_document,
)
from .contracts.source_fingerprint import SourceFingerprint
from .errors import ResumeStateError
from .image_request_identity import ImageRequestIdentity
from .parse_image_resume_state_document import parse_image_resume_state_document
from .video_job_state import (
    VideoAudioState,
    VideoFrameGroupState,
    VideoJobState,
    VideoShortAudioState,
)


_ROOT_KEYS = frozenset(
    {"state_version", "source", "frame_groups", "audio", "final_markdown_sha256"}
)
_SOURCE_KEYS = frozenset({"uri", "byte_size", "sha256"})
_GROUP_KEYS = frozenset(
    {
        "index",
        "frame_indices",
        "frame_timestamps_seconds",
        "identity",
        "image_state",
    }
)
_IDENTITY_KEYS = frozenset(
    {
        "request_fingerprint",
        "identity_version",
        "processor_name",
        "processor_version",
        "sources",
    }
)
_AUDIO_KEYS = frozenset(
    {
        "state",
        "mode",
        "interval_minutes",
        "model",
        "artifact",
        "duration_seconds",
        "short_state",
        "long_state",
    }
)
_SHORT_KEYS = frozenset(
    {
        "request_fingerprint",
        "markdown",
        "markdown_sha256",
        "status",
        "warnings",
        "metadata",
        "no_speech",
    }
)


def parse_video_job_state(raw: bytes) -> VideoJobState:
    """Reject duplicate keys, schema drift, and invalid nested state."""
    try:
        if type(raw) is not bytes:
            raise TypeError
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        if type(document) is not dict or frozenset(document) != _ROOT_KEYS:
            raise ValueError
        groups_document = document["frame_groups"]
        audio_document = document["audio"]
        if type(groups_document) is not list or not groups_document:
            raise ValueError
        if type(audio_document) is not dict or frozenset(audio_document) != _AUDIO_KEYS:
            raise ValueError
        groups = []
        for group in groups_document:
            if type(group) is not dict or frozenset(group) != _GROUP_KEYS:
                raise ValueError
            identity_document = group["identity"]
            if (
                type(identity_document) is not dict
                or frozenset(identity_document) != _IDENTITY_KEYS
                or type(identity_document["sources"]) is not list
            ):
                raise ValueError
            frame_indices = group["frame_indices"]
            timestamps = group["frame_timestamps_seconds"]
            if type(frame_indices) is not list or type(timestamps) is not list:
                raise ValueError
            identity = ImageRequestIdentity(
                request_fingerprint=identity_document["request_fingerprint"],
                identity_version=identity_document["identity_version"],
                processor_name=identity_document["processor_name"],
                processor_version=identity_document["processor_version"],
                sources=tuple(
                    _parse_source(source) for source in identity_document["sources"]
                ),
            )
            image_document = group["image_state"]
            groups.append(
                VideoFrameGroupState(
                    index=group["index"],
                    frame_indices=tuple(frame_indices),
                    frame_timestamps_seconds=tuple(timestamps),
                    identity=identity,
                    image_state=(
                        None
                        if image_document is None
                        else parse_image_resume_state_document(image_document)
                    ),
                )
            )
        short_document = audio_document["short_state"]
        if short_document is not None and (
            type(short_document) is not dict
            or frozenset(short_document) != _SHORT_KEYS
            or type(short_document["warnings"]) is not list
        ):
            raise ValueError
        short_state = (
            None
            if short_document is None
            else VideoShortAudioState(
                request_fingerprint=short_document["request_fingerprint"],
                markdown=short_document["markdown"],
                markdown_sha256=short_document["markdown_sha256"],
                status=short_document["status"],
                warnings=tuple(short_document["warnings"]),
                metadata=short_document["metadata"],
                no_speech=short_document["no_speech"],
            )
        )
        long_document = audio_document["long_state"]
        return VideoJobState(
            state_version=document["state_version"],
            source=_parse_source(document["source"]),
            frame_groups=tuple(groups),
            audio=VideoAudioState(
                state=audio_document["state"],
                mode=audio_document["mode"],
                interval_minutes=audio_document["interval_minutes"],
                model=audio_document["model"],
                artifact=(
                    None
                    if audio_document["artifact"] is None
                    else _parse_source(audio_document["artifact"])
                ),
                duration_seconds=audio_document["duration_seconds"],
                short_state=short_state,
                long_state=(
                    None
                    if long_document is None
                    else parse_long_audio_partial_state_document(long_document)
                ),
            ),
            final_markdown_sha256=document["final_markdown_sha256"],
        )
    except ResumeStateError:
        raise
    except Exception:
        raise ResumeStateError(
            "The video resume journal is corrupt or has an unsupported schema.",
            code="RESUME_STATE_INVALID",
        ) from None


def _parse_source(document: object) -> SourceFingerprint:
    if type(document) is not dict or frozenset(document) != _SOURCE_KEYS:
        raise ValueError
    return SourceFingerprint(
        uri=document["uri"],
        byte_size=document["byte_size"],
        sha256=document["sha256"],
    )


class _DuplicateKey(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise _DuplicateKey
        document[key] = value
    return document


def _reject_constant(_value: str) -> object:
    raise ValueError
