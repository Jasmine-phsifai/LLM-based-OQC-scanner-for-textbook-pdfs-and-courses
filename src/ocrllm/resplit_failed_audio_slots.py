"""Explicitly subdivide failed ranges inside their existing audio checkpoint."""
from dataclasses import replace

from .errors import ConfigError
from .merged_audio_resume_state import MergedAudioSlot, SPLIT_AUDIO_RESUME_STATE_VERSION, GAP_AUDIO_RESUME_STATE_VERSION


def resplit_failed_audio_slots(state, *, interval_minutes, slot_indices=None, only_output_limit=False):
    """Keep settled ranges and refine failed ranges without nested state trees.

    Automatic recovery is limited to one subdivision of an original slot.
    Explicit maintenance can choose a smaller interval for remaining failed
    children, retaining every already settled child's text and source range.
    """
    if type(interval_minutes) is not int or interval_minutes <= 0:
        raise ConfigError('failed_slice_minutes must be a positive integer.', code='CONFIG_INVALID')
    changed = False
    slots = []
    for slot in state.slots:
        if (slot.status != 'failed'
            or (slot_indices is not None and slot.index not in slot_indices)
            or (only_output_limit and slot.subslots)):
            slots.append(slot)
            continue
        children = []
        parent_changed = False
        for candidate in slot.subslots or (slot,):
            span = interval_minutes * 60.0
            eligible = (candidate.status == 'failed'
                        and candidate.logical_end_seconds-candidate.logical_start_seconds > span)
            if only_output_limit:
                description = candidate.error_description or ''
                eligible = eligible and ('provider_code=output_token_limit ' in description
                                         or 'provider_code=output_token_limit]' in description)
            if not eligible:
                children.append(candidate)
                continue
            start = candidate.logical_start_seconds
            while start < candidate.logical_end_seconds:
                end = min(start + span, candidate.logical_end_seconds)
                children.append(MergedAudioSlot(
                    index=len(children), logical_start_seconds=start, logical_end_seconds=end,
                    actual_start_seconds=(candidate.actual_start_seconds if start == candidate.logical_start_seconds else start),
                    actual_end_seconds=(candidate.actual_end_seconds if end == candidate.logical_end_seconds else end),
                ))
                start = end
            parent_changed = True
        if parent_changed:
            slots.append(replace(slot, subslots=tuple(replace(child, index=index) for index, child in enumerate(children))))
            changed = True
        else:
            slots.append(slot)
    return replace(state, state_version=(GAP_AUDIO_RESUME_STATE_VERSION if state.state_version == GAP_AUDIO_RESUME_STATE_VERSION else SPLIT_AUDIO_RESUME_STATE_VERSION), slots=tuple(slots)) if changed else state
