"""Adapt one ProviderModel to the existing built-in image call boundary."""

from __future__ import annotations

from ...config import Config
from .provider_settings import OpenAICompatibleSettings
from .recognize_openai_compatible_images import (
    recognize_openai_compatible_images,
)


class OpenAICompatibleProvider:
    """Run one exact model without owning fallback, retry, or batching."""

    __slots__ = ("_model", "_settings", "_vendor")

    def __init__(
        self,
        *,
        vendor: str,
        model: str,
        settings: OpenAICompatibleSettings,
    ) -> None:
        self._vendor = vendor
        self._model = model
        self._settings = settings

    def recognize_images(self, image_paths, *, prompt: str, config: Config):
        """Recognize one already planned image group."""
        return recognize_openai_compatible_images(
            image_paths,
            prompt=prompt,
            vendor=self._vendor,
            model=self._model,
            settings=self._settings,
            timeout_seconds=config.timeout_seconds,
        )
