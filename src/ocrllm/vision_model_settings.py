"""Immutable model identity and image-capability settings."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import ConfigError
from .image_group_limits import MAX_IMAGE_GROUP_COUNT


@dataclass(frozen=True, slots=True)
class VisionModelSettings:
    """Select one vision model and an optional ordered recovery chain."""

    name: str | None = None
    candidate_models: tuple[str, ...] = ()
    maximum_images_per_request: int | None = None

    def __post_init__(self) -> None:
        if self.name is not None and (
            type(self.name) is not str
            or not self.name
            or self.name != self.name.strip()
            or any(ord(character) < 32 or ord(character) == 127 for character in self.name)
        ):
            raise ConfigError(
                "VisionModelSettings.name must be nonempty exact text when set.",
                code="CONFIG_INVALID",
            ) from None
        if type(self.candidate_models) is not tuple or any(
            type(model) is not str or not model.strip()
            for model in self.candidate_models
        ):
            raise ConfigError(
                "VisionModelSettings.candidate_models must be a tuple of nonempty text.",
                code="CONFIG_INVALID",
            ) from None
        if len(set(self.candidate_models)) != len(self.candidate_models):
            raise ConfigError(
                "VisionModelSettings.candidate_models must not contain duplicates.",
                code="CONFIG_INVALID",
            ) from None
        maximum = self.maximum_images_per_request
        if maximum is not None and (
            type(maximum) is not int or not 1 <= maximum <= MAX_IMAGE_GROUP_COUNT
        ):
            raise ConfigError(
                "VisionModelSettings.maximum_images_per_request must be None or "
                f"an integer in [1, {MAX_IMAGE_GROUP_COUNT}].",
                code="CONFIG_INVALID",
            ) from None
