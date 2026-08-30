"""Compose ordered merged-image slots and failed markers."""

from __future__ import annotations

from .merged_image_resume_state import MergedImageSlot


def compose_merged_image_markdown(slots: tuple[MergedImageSlot, ...]) -> str:
    """Return one deterministic Markdown document in original slot order."""
    sections: list[str] = []
    for slot in slots:
        source_label = _source_label(slot.source_indexes)
        heading = f"## OCRLLM image slot {slot.index + 1} ({source_label})"
        if slot.status == "settled":
            assert slot.markdown is not None
            body = slot.markdown.strip()
        else:
            code = slot.error_code or "UNRESOLVED"
            body = (
                "<!-- OCRLLM_FAILED_IMAGE_SLOT "
                f"index={slot.index + 1} sources={source_label} code={code} -->"
            )
        sections.append(f"{heading}\n\n{body}")
    return "\n\n".join(sections).rstrip() + "\n"


def _source_label(source_indexes: tuple[int, ...]) -> str:
    first = source_indexes[0] + 1
    last = source_indexes[-1] + 1
    return str(first) if first == last else f"{first}-{last}"
