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
        if slot.subslots:
            child_sections = []
            for child in slot.subslots:
                child_heading = (f"### 音频区间 {child.logical_start_seconds:.3f}-"
                                 f"{child.logical_end_seconds:.3f}s")
                if child.status == 'settled':
                    child_body = (f"<!-- OCRLLM_NO_SPEECH_AUDIO_SUBSLOT parent={slot.index+1} index={child.index+1} -->"
                                  if child.no_speech else child.markdown.strip())
                else:
                    label = 'FAIL' if child.status == 'failed' else 'PENDING'
                    child_body = (f"**{label}**：此区间尚无可靠转写。\n\n"
                                  f"<!-- OCRLLM_FAILED_AUDIO_SUBSLOT parent={slot.index+1} "
                                  f"index={child.index+1} code={child.error_code or 'UNRESOLVED'} "
                                  f"actual={child.actual_start_seconds:.3f}-{child.actual_end_seconds:.3f}s -->")
                child_sections.append(f"{child_heading}\n\n{child_body}")
            body = '\n\n'.join(child_sections)
        elif slot.status == "settled" and slot.no_speech:
            body = f"<!-- OCRLLM_NO_SPEECH_AUDIO_SLOT index={slot.index + 1} -->"
        elif slot.status == "settled":
            assert slot.markdown is not None
            body = slot.markdown.strip()
        else:
            code = slot.error_code or "UNRESOLVED"
            body = (
                "<!-- OCRLLM_FAILED_AUDIO_SLOT "
                f"index={slot.index + 1} code={code} "
                f"actual={slot.actual_start_seconds:.3f}-"
                f"{slot.actual_end_seconds:.3f}s -->"
            )
        sections.append(f"{heading}\n\n{body}")
    return "\n\n".join(sections).rstrip() + "\n"
