"""Represent one long-audio job's owned output paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


LONG_AUDIO_RESULT_NAME = "result.md"
LONG_AUDIO_RESUME_STATE_NAME = ".ocrllm-long-audio-resume.json"


@dataclass(frozen=True, slots=True)
class LongAudioOutputPaths:
    """Keep the job directory, final result, and temporary resume sidecar."""

    root: Path
    result: Path
    resume_state: Path
