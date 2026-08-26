"""Remove settled long-audio recovery state without hiding cleanup failure."""

from __future__ import annotations

from pathlib import Path

from ..processor_output import ProcessorOutput


def remove_long_audio_temporary_state(
    state_path: Path,
    output: ProcessorOutput,
) -> ProcessorOutput:
    """Remove temporary state or return the settled output as partial."""
    try:
        state_path.unlink()
        return output
    except (OSError, ValueError):
        warning = "The temporary long-audio resume state could not be removed."
        metadata = dict(output.metadata)
        metadata["resume_state_removed"] = False
        return ProcessorOutput(
            media_type=output.media_type,
            markdown=output.markdown,
            status="partial",
            warnings=output.warnings + (warning,),
            metadata=metadata,
        )
