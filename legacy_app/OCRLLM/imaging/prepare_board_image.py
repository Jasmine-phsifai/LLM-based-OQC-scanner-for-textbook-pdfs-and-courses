"""Prepare one complete board image without cropping or perspective changes."""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image

from OCRLLM.core.utils import atomic_save_image


def prepare_board_image(
    source_path: str,
    output_path: str,
    *,
    max_side: int,
    quality: int,
) -> str:
    """Copy or downscale the complete source image into a provider-safe file."""
    source = Path(source_path)
    if source.suffix.casefold() in {".heic", ".heif"}:
        try:
            import pillow_heif
        except ImportError as error:
            raise RuntimeError(
                "需要安装 pillow-heif 才能读取 HEIC/HEIF 图片"
            ) from error
        pillow_heif.register_heif_opener()

    with Image.open(source) as opened:
        opened.load()
        image = opened.copy()

    width, height = image.size
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    requires_resize = max(width, height) > max_side
    if not requires_resize and source.suffix.casefold() == destination.suffix.casefold():
        shutil.copy2(source, destination)
        return str(destination)

    if image.mode not in {"RGB", "L"}:
        image = image.convert("RGB")
    if requires_resize:
        scale = max_side / max(width, height)
        image = image.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.Resampling.LANCZOS,
        )

    save_options = {"quality": quality} if destination.suffix.casefold() in {
        ".jpg",
        ".jpeg",
        ".webp",
    } else {}
    atomic_save_image(image, str(destination), **save_options)
    return str(destination)
