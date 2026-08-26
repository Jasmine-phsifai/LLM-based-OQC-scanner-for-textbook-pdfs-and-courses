"""Bind settled long-audio slots to one ordered request plan."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .fingerprint_long_audio_request import LONG_AUDIO_REQUEST_IDENTITY_VERSION
from .long_audio_settled_slot import LongAudioSettledSlot


LONG_AUDIO_PARTIAL_STATE_VERSION = "ocrllm.long-audio-partial.v3"
_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True, kw_only=True)
class LongAudioPartialState:
    """Store the completed prefix of one whole-file or interval request plan."""

    state_version: str
    identity_version: str
    mode: Literal["whole", "interval"]
    interval_minutes: int | None
    request_fingerprints: tuple[str, ...]
    slots: tuple[LongAudioSettledSlot, ...] = ()

    def __post_init__(self) -> None:
        if (
            type(self.state_version) is not str
            or self.state_version != LONG_AUDIO_PARTIAL_STATE_VERSION
        ):
            raise ValueError("long-audio partial state version is unsupported") from None
        if (
            type(self.identity_version) is not str
            or self.identity_version != LONG_AUDIO_REQUEST_IDENTITY_VERSION
        ):
            raise ValueError("long-audio request identity version is unsupported") from None
        if self.mode not in ("whole", "interval"):
            raise ValueError("long-audio mode is invalid") from None
        if self.mode == "whole":
            if self.interval_minutes is not None:
                raise ValueError("whole long-audio state has an interval") from None
        elif type(self.interval_minutes) is not int or self.interval_minutes <= 0:
            raise ValueError("interval long-audio state has no valid minutes") from None
        if type(self.request_fingerprints) is not tuple:
            raise TypeError("request_fingerprints must be an exact tuple") from None
        if not self.request_fingerprints or any(
            type(fingerprint) is not str or _SHA256.fullmatch(fingerprint) is None
            for fingerprint in self.request_fingerprints
        ):
            raise ValueError("long-audio request fingerprints are invalid") from None
        if len(set(self.request_fingerprints)) != len(self.request_fingerprints):
            raise ValueError("long-audio request fingerprints are duplicated") from None
        if type(self.slots) is not tuple:
            raise TypeError("slots must be an exact tuple") from None
        if any(type(slot) is not LongAudioSettledSlot for slot in self.slots):
            raise ValueError("long-audio settled slots are invalid") from None
        if len(self.slots) > len(self.request_fingerprints):
            raise ValueError(
                "long-audio slots do not match the ordered request plan"
            ) from None
        for expected_index, slot in enumerate(self.slots):
            if (
                slot.window_index != expected_index
                or slot.request_fingerprint
                != self.request_fingerprints[expected_index]
            ):
                raise ValueError(
                    "long-audio slots do not match the ordered request plan"
                ) from None
