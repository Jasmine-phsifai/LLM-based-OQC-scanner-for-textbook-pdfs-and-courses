"""Route one validated image group through the selected recognition strategy."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from .config import Config
from .errors import Cancelled, OutputError
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

        try:
            output = recognize_images_with_rapidocr(
                validated_paths,
                profile=profile,
                config=config,
            )
        except Cancelled as error:
            error._add_safe_detail("provider_calls_attempted", 0)
            raise
        if slot_checkpoint is not None:
            try:
                slot_checkpoint.verify_snapshots()
            except OutputError as error:
                error._add_safe_detail("provider_calls_attempted", 0)
                raise
        return output
    from .processors.recognize_images import recognize_images

    return recognize_images(
        validated_paths,
        profile=profile,
        config=config,
        slot_checkpoint=slot_checkpoint,
    )
