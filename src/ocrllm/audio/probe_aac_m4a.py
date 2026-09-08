"""Inspect the explicitly supported 24 kHz AAC/M4A course archive input."""
from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path

from ..errors import InvalidSource
from .load_audio_ffmpeg_executable import load_audio_ffmpeg_executable


def probe_aac_m4a(source: Path) -> float:
    """Read container duration and audio codec without transcoding the course."""
    try:
        result = subprocess.run(
            [str(load_audio_ffmpeg_executable()), '-nostdin', '-hide_banner', '-i', str(source)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            timeout=30, check=False, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise InvalidSource('The AAC/M4A archive cannot be inspected.', code='SOURCE_UNREADABLE') from error
    description = result.stderr.decode('utf-8', errors='replace')
    duration = re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)', description)
    if not duration or not re.search(r'Audio: aac\b[^\n]*\b24000 Hz\b', description):
        raise InvalidSource('The M4A course input must contain 24 kHz AAC audio and a known duration.', code='SOURCE_INVALID')
    seconds = int(duration[1])*3600 + int(duration[2])*60 + float(duration[3])
    if not math.isfinite(seconds) or seconds <= 0:
        raise InvalidSource('The AAC/M4A archive has no positive duration.', code='SOURCE_INVALID')
    return seconds
