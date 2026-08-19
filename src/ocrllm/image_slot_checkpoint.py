"""Persist completed image workflow slots as each one finishes."""

from __future__ import annotations

from pathlib import Path

from .image_request_identity import ImageRequestIdentity
from .image_resume_state import IMAGE_RESUME_STATE_VERSION, ImageResumeState
from .image_slot_state import ImageSlotState
from .output.save_image_resume_state_atomically import (
    save_image_resume_state_atomically,
)


class ImageSlotCheckpoint:
    """Durable slot-indexed checkpoint for one in-flight image request.

    Each completed workflow pass is persisted immediately, so a crash after
    any paid call leaves that call's validated output on disk. Slots are
    reusable only by the same provider and model that produced them.
    """

    def __init__(
        self,
        identity: ImageRequestIdentity,
        state_path: Path,
        *,
        profile: str,
        seeded_slots: tuple[ImageSlotState, ...] = (),
    ) -> None:
        self._identity = identity
        self._state_path = state_path
        self._profile = profile
        self._slots: dict[str, ImageSlotState] = {
            slot.slot_id: slot for slot in seeded_slots
        }

    @property
    def slots(self) -> tuple[ImageSlotState, ...]:
        """Return every persisted slot in completion order."""
        return tuple(self._slots.values())

    def reusable_slot(
        self,
        slot_id: str,
        *,
        provider: str | None,
        model: str | None,
    ) -> ImageSlotState | None:
        """Return a persisted slot only for the same provider and model."""
        slot = self._slots.get(slot_id)
        if slot is None or slot.provider != provider or slot.model != model:
            return None
        return slot

    def persist_slot(self, slot: ImageSlotState) -> None:
        """Durably record one completed slot before the next call starts."""
        self._slots[slot.slot_id] = slot
        state = ImageResumeState(
            state_version=IMAGE_RESUME_STATE_VERSION,
            identity_version=self._identity.identity_version,
            request_fingerprint=self._identity.request_fingerprint,
            processor_name=self._identity.processor_name,
            processor_version=self._identity.processor_version,
            sources=self._identity.sources,
            markdown="",
            media_type="image",
            profile=self._profile,
            status="partial",
            hotwords=(),
            warnings=(),
            slots=self.slots,
        )
        save_image_resume_state_atomically(self._state_path, state)
