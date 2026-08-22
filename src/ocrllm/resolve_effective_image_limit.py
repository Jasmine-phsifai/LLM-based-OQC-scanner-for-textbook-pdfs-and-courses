"""Resolve the strictest image count limit for one configured workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .image_group_limits import MAX_IMAGE_GROUP_COUNT

if TYPE_CHECKING:
    from .config import Config


def resolve_effective_image_limit(config: Config) -> tuple[int, str]:
    """Return the strictest pre-upload limit and its safe policy source."""
    candidates = [
        (MAX_IMAGE_GROUP_COUNT, "library_safety"),
        (
            config.execution.maximum_images_per_request,
            "recognition_execution_policy",
        ),
    ]
    configured_model_limit = config.vision_model.maximum_images_per_request
    if configured_model_limit is not None:
        candidates.append((configured_model_limit, "vision_model_settings"))
    return min(candidates, key=lambda candidate: candidate[0])
