"""One batch item's outcome: exactly one of a result or a typed failure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .errors import OCRLLMError

if TYPE_CHECKING:
    from .result import RecognitionResult


@dataclass(frozen=True, slots=True, kw_only=True)
class BatchItemOutcome:
    """Report one source's fate without hiding it behind a raised exception."""

    index: int
    result: RecognitionResult | None = None
    error: OCRLLMError | None = None

    def __post_init__(self) -> None:
        if type(self.index) is not int or self.index < 0:
            raise TypeError("batch item index must be a non-negative integer") from None
        if (self.result is None) == (self.error is None):
            raise ValueError(
                "batch item outcome must carry exactly one of result or error"
            ) from None
        if self.error is not None and not isinstance(self.error, OCRLLMError):
            raise TypeError("batch item error must be an OCRLLMError") from None

    @property
    def succeeded(self) -> bool:
        """Return True when this item produced a recognition result."""
        return self.result is not None
