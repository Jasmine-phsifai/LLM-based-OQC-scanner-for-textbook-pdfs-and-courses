"""Serialize one validated image resume state as canonical UTF-8 JSON."""

from __future__ import annotations

import json

from .image_resume_state import ImageResumeState
from .image_resume_state_to_document import image_resume_state_to_document


def serialize_image_resume_state(state: ImageResumeState) -> bytes:
    """Return deterministic state bytes without runtime or secret fields."""
    document = image_resume_state_to_document(state)
    return (
        json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
