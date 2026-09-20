"""Inspect narrow service-failure recovery without changing image checkpoints."""
from pathlib import Path


def image_service_recovery_slots(state, batch_id=None) -> frozenset[int]:
    """Keep the original plan; only canonical, saved service failures qualify."""
    if state.provider_cleanup_failed:
        return frozenset()
    reserved = state.service_recovery_reservations.get(batch_id, ())
    return frozenset(slot.index for slot in state.slots
                     if slot.index not in reserved and slot.status == "failed" and slot.error_code in
                     {"PROVIDER_UNAVAILABLE", "PROVIDER_TIMEOUT"})


def inspect_image_service_recovery(output_path: str | Path, *, service_recovery_batch_id: str | None = None) -> dict[str, object]:
    """Return eligibility, never permission to dispatch or a new retry budget.

    A supplied batch ID excludes its already reserved slots. Without an ID the
    query reports raw service candidates, not remaining campaign allowance.
    Missing, incompatible, unreadable, or cleanup-unconfirmed state is denied.
    The caller owns its bounded recovery campaign and must prevent concurrent
    dispatch; resume revalidates the saved plan and eligibility under its claim.
    """
    from .errors import OCRLLMError
    from .output.load_merged_image_resume_state import load_merged_image_resume_state
    from .output.resolve_resume_state_path import resolve_resume_state_path
    if service_recovery_batch_id is not None:
        validate_service_recovery_batch_id(service_recovery_batch_id)
    count = 0
    try:
        state = load_merged_image_resume_state(resolve_resume_state_path(Path(output_path)))
    except OCRLLMError as error:
        reason = error.code
    else:
        count = len(image_service_recovery_slots(state, service_recovery_batch_id))
        reason = ("provider_cleanup_unconfirmed" if state.provider_cleanup_failed
                  else "service_failures_available" if count else "no_service_failures")
    return {"service_recovery_available": bool(count),
            "service_recovery_slot_count": count, "reason": reason}


def validate_service_recovery_batch_id(value):
    from .errors import ConfigError
    if type(value) is not str or not value.strip():
        raise ConfigError("Service recovery requires a nonempty batch ID.", code="CONFIG_INVALID")
