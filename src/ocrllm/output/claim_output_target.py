"""Claim one output target for one in-process recognition."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Iterator

from ..errors import OutputError, OutputExists


_CLAIMS_GUARD = Lock()
_CLAIMED_TARGETS: set[str] = set()


@contextmanager
def claim_output_target(output_path: Path) -> Iterator[None]:
    """Reject overlapping ownership while allowing later sequential reuse."""
    try:
        claim_key = os.path.normcase(str(output_path.resolve(strict=False)))
    except (OSError, RuntimeError, ValueError) as error:
        raise OutputError(
            "The requested Markdown output path could not be resolved.",
            code="OUTPUT_PATH_INVALID",
        ) from error

    with _CLAIMS_GUARD:
        if claim_key in _CLAIMED_TARGETS:
            raise OutputExists(
                "The requested Markdown output is already owned by another "
                "recognition in this process."
            ) from None
        _CLAIMED_TARGETS.add(claim_key)

    try:
        yield
    finally:
        with _CLAIMS_GUARD:
            _CLAIMED_TARGETS.remove(claim_key)
