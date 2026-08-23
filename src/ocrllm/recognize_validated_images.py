"""Route one validated image group through the selected recognition strategy."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from .config import Config
from .processor_output import ProcessorOutput

if TYPE_CHECKING:
    from .image_slot_checkpoint import ImageSlotCheckpoint


def recognize_validated_images(
    validated_paths: Sequence[Path],
    *,
    profile: str,
    config: Config,
    slot_checkpoint: ImageSlotCheckpoint | None = None,
) -> ProcessorOutput:
    """Run local OCR or the unified provider-backed board processor."""
    if config.image_mode == "ocr":
        from .local_ocr.recognize_images_with_rapidocr import (
            recognize_images_with_rapidocr,
        )

        output = recognize_images_with_rapidocr(
            validated_paths,
            profile=profile,
            config=config,
        )
        if slot_checkpoint is not None:
            slot_checkpoint.verify_snapshots()
        return output
    from .processors.recognize_images import recognize_images

    return recognize_images(
        validated_paths,
        profile=profile,
        config=config,
        slot_checkpoint=slot_checkpoint,
    )
