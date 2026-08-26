"""Resolve the fixed sibling path for image resume state."""

from __future__ import annotations

from pathlib import Path


def resolve_image_resume_state_path(output_path: Path) -> Path:
    """Return the resume-state sibling owned by one Markdown output."""
    return output_path.with_name(f"{output_path.stem}.ocrllm-state.json")
