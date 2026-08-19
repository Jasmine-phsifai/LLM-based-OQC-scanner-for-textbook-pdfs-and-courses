"""Resolve the documented image count cap for one supported DashScope model."""

from __future__ import annotations

from .resolve_dashscope_model import SUPPORTED_DASHSCOPE_MODELS


_MAXIMUM_IMAGES_BY_MODEL = {
    model: 10 for model in SUPPORTED_DASHSCOPE_MODELS
}


def resolve_dashscope_maximum_images(model: str) -> int:
    """Return the pre-upload image cap for one already resolved model."""
    return _MAXIMUM_IMAGES_BY_MODEL.get(model, 10)
