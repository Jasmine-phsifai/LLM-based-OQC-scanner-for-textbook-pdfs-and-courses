"""Compose ordered merged-audio slots and explicit terminal markers."""

from __future__ import annotations

from .merged_audio_resume_state import MergedAudioSlot


def compose_merged_audio_markdown(slots: tuple[MergedAudioSlot, ...]) -> str:
    """Return one deterministic Markdown document in original slice order."""
    sections: list[str] = []
    for slot in slots:
        range_label = (
            f"{slot.logical_start_seconds:.3f}-"
            f"{slot.logical_end_seconds:.3f}s"
        )
        heading = f"## OCRLLM audio slot {slot.index + 1} ({range_label})"
        if slot.status == "settled" and slot.no_speech:
            body = f"<!-- OCRLLM_NO_SPEECH_AUDIO_SLOT index={slot.index + 1} -->"
        elif slot.status == "settled":
            assert slot.markdown is not None
            body = slot.markdown.strip()
        else:
            code = slot.error_code or "UNRESOLVED"
            body = (
                "<!-- OCRLLM_FAILED_AUDIO_SLOT "
                f"index={slot.index + 1} code={code} -->"
            )
        sections.append(f"{heading}\n\n{body}")
    return "\n\n".join(sections).rstrip() + "\n"
