"""Represent one long-audio job's owned output paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LongAudioOutputPaths:
    """Keep the job directory, final result, and temporary resume sidecar."""

    root: Path
    result: Path
    resume_state: Path
