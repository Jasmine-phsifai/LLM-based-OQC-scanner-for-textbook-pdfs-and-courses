"""Remove internal exception links before exposing an OCRLLM error."""

from __future__ import annotations

from .errors import OCRLLMError


def clear_public_error(error: OCRLLMError) -> None:
    """Erase internal traceback and exception-chain references in place."""
    error.__cause__ = None
    error.__context__ = None
    error.__suppress_context__ = True
    error.__traceback__ = None
