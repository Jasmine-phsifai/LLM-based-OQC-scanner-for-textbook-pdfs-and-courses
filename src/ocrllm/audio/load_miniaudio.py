"""Load the optional MP3 decoder only when audio validation runs."""

from __future__ import annotations

from typing import Any

from ..errors import DependencyMissing


def load_miniaudio() -> Any:
    """Return miniaudio without adding it to the base import path."""

    try:
        import miniaudio
    except (ImportError, OSError):
        raise DependencyMissing(
            "MP3 validation requires the optional 'audio' dependencies.",
            details={
                "extra": "audio",
                "required_distribution": "miniaudio>=1.71,<2",
            },
        ) from None
    return miniaudio
