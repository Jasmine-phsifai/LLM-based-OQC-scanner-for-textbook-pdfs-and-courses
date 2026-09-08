"""Inspect completion of a caller-owned OCRLLM merged Markdown target."""
from pathlib import Path
from typing import Literal


def inspect_markdown_job(output_path: str | Path) -> Literal['missing', 'pending', 'complete']:
    """Return publication status without exposing checkpoint structure.

    Use only for a target exclusively owned by OCRLLM merged recognition APIs.
    Pending includes partial output and interrupted work: ordinary resume reuses
    settled slots. A complete output is published before its checkpoint is
    removed; leftover checkpoints are safely resumed without new inference.
    This does not authenticate arbitrary Markdown supplied by another writer.
    """
    from .output.resolve_resume_state_path import resolve_resume_state_path
    path = Path(output_path)
    if resolve_resume_state_path(path).exists():
        return 'pending'
    return 'complete' if path.is_file() else 'missing'
