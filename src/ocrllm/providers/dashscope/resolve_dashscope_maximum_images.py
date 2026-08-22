"""Resolve the documented image count cap for one resolved DashScope model."""

from __future__ import annotations

DASHSCOPE_MAXIMUM_IMAGES_PER_REQUEST = 10


def resolve_dashscope_maximum_images(model: str) -> int:
    """Return the pre-upload image cap for one already resolved model."""
    return DASHSCOPE_MAXIMUM_IMAGES_PER_REQUEST
