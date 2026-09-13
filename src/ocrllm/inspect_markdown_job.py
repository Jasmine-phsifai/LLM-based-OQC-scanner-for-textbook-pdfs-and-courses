"""Inspect completion of a caller-owned OCRLLM merged Markdown target."""
from pathlib import Path
from typing import Literal


def inspect_markdown_job(output_path: str | Path) -> Literal['missing', 'pending', 'complete', 'complete_with_gaps']:
    """Return publication status without exposing checkpoint structure.

    Use only for a target exclusively owned by OCRLLM merged recognition APIs.
    Pending includes partial output and interrupted work: ordinary resume reuses
    settled slots. A complete output is published before its checkpoint is
    removed; leftover checkpoints are safely resumed without new inference.
    Explicitly accepted audio gaps retain their checkpoint and return
    complete_with_gaps; inspect_audio_completion provides their gap metadata.
    This does not authenticate arbitrary Markdown supplied by another writer.
    """
    from .output.resolve_resume_state_path import resolve_resume_state_path
    path = Path(output_path)
    state_path = resolve_resume_state_path(path)
    if state_path.exists():
        from .output.load_merged_audio_resume_state import load_merged_audio_resume_state
        from .errors import OCRLLMError
        try:
            state = load_merged_audio_resume_state(state_path)
        except OCRLLMError:
            return 'pending'
        from .is_audio_markdown_published import is_audio_markdown_published
        published = is_audio_markdown_published(state, path)
        if state.accepted_with_gaps and published:
            return 'complete_with_gaps'
        if state.audio_output_limit_policy and published and all(slot.status == 'settled' for slot in state.slots):
            return 'complete'
        return 'pending'
    return 'complete' if path.is_file() else 'missing'
