"""Atomically write one OpenCV image to a Unicode path."""

from __future__ import annotations

import os

import cv2
import numpy as np

from OCRLLM.core.utils import atomic_temp_path


def imwrite_unicode(path: str, image: np.ndarray, params=None) -> bool:
    """Encode and atomically publish one OpenCV image."""
    extension = os.path.splitext(path)[1]
    result, encoded = (
        cv2.imencode(extension, image, params)
        if params
        else cv2.imencode(extension, image)
    )
    if not result:
        return False
    temporary_path = atomic_temp_path(path)
    encoded.tofile(temporary_path)
    os.replace(temporary_path, path)
    return True
