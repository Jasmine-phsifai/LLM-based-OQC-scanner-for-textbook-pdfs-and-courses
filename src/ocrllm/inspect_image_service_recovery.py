"""Inspect narrow service-failure recovery without changing image checkpoints."""
from pathlib import Path


def image_service_recovery_slots(state) -> frozenset[int]:
    """Keep the original plan; only canonical, saved service failures qualify."""
    if state.provider_cleanup_failed:
        return frozenset()
    return frozenset(slot.index for slot in state.slots
                     if slot.status == "failed" and slot.error_code in
                     {"PROVIDER_UNAVAILABLE", "PROVIDER_TIMEOUT"})


def inspect_image_service_recovery(output_path: str | Path) -> dict[str, object]:
    """Return eligibility, never permission to dispatch or a new retry budget.

    Missing, incompatible, unreadable, or cleanup-unconfirmed state is denied.
    The caller owns its bounded recovery campaign and must prevent concurrent
    dispatch; resume revalidates the saved plan and eligibility under its claim.
    """
    from .errors import OCRLLMError
    from .output.load_merged_image_resume_state import load_merged_image_resume_state
    from .output.resolve_resume_state_path import resolve_resume_state_path
    count = 0
    try:
        state = load_merged_image_resume_state(resolve_resume_state_path(Path(output_path)))
    except OCRLLMError as error:
        reason = error.code
    else:
        count = len(image_service_recovery_slots(state))
        reason = ("provider_cleanup_unconfirmed" if state.provider_cleanup_failed
                  else "service_failures_available" if count else "no_service_failures")
    return {"service_recovery_available": bool(count),
            "service_recovery_slot_count": count, "reason": reason}
