"""Structural protocol for one synchronous image-recognition capability."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ..config import Config
    from .vision_provider_response import VisionProviderResponse


class VisionProvider(Protocol):
    """Consume validated snapshot paths before returning recognition Markdown."""

    def recognize_images(
        self,
        image_paths: Sequence[Path],
        *,
        prompt: str,
        config: Config,
    ) -> str | VisionProviderResponse:
        """Recognize one ordered image group synchronously."""
        ...
