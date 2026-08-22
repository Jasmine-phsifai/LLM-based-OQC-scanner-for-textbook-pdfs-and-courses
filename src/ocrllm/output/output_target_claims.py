"""Retain process-local output target claims for one public operation."""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from threading import Lock
from types import TracebackType

from .claim_output_target import claim_output_target


class OutputTargetClaims:
    """Own output claims until a direct call or whole batch has settled."""

    def __init__(self) -> None:
        self._claims = ExitStack()
        self._lock = Lock()

    def __enter__(self) -> OutputTargetClaims:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        with self._lock:
            self._claims.close()

    def claim(self, output_path: Path) -> None:
        """Claim one target and retain it for this owner's lifetime."""
        with self._lock:
            self._claims.enter_context(claim_output_target(output_path))
