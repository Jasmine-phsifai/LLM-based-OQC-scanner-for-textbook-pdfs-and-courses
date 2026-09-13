"""Refine exhausted audio ranges while keeping the existing flat checkpoint."""
from dataclasses import replace

from .audio_gap_summary import is_output_limit_failure
from .merged_audio_resume_state import BOUNDED_AUDIO_RESUME_STATE_VERSION, MergedAudioSlot


def upgrade_audio_output_limit_state(state, policy):
    """Adopt old failed ranges without inventing unrecorded request history.

    An old flat child already consumed one subdivision level. V1/v2 records
    prove only their latest failure; v3 consecutive failure counts are retained.
    """
    if state.audio_output_limit_policy is not None:
        if state.audio_output_limit_policy != policy:
            from .errors import ResumeStateError
            raise ResumeStateError('The saved audio recovery policy cannot be reset.',
                                   code='RESUME_STATE_MISMATCH')
        return state

    def adopt(slot, depth):
        # An old aggregate parent's latest error may belong to a child.
        # It does not prove a request on the whole parent range.
        failed = is_output_limit_failure(slot) and not slot.subslots
        attempts = max(slot.output_limit_attempts, int(failed))
        evidence = ()
        if failed:
            evidence = ({'start_seconds': slot.logical_start_seconds,
                         'end_seconds': slot.logical_end_seconds,
                         'split_depth': depth, 'attempt': attempts,
                         'historical_attempts_unknown': slot.output_limit_attempts == 0,
                         'description': slot.error_description},)
        return replace(slot, split_depth=depth, recovery_attempts=attempts,
                       output_limit_evidence=evidence,
                       subslots=tuple(adopt(child, 1) for child in slot.subslots))

    return replace(state, state_version=BOUNDED_AUDIO_RESUME_STATE_VERSION,
                   audio_output_limit_policy=policy,
                   slots=tuple(adopt(slot, 0) for slot in state.slots))


def bisect_failed_audio_slots(state, *, slot_index):
    """Split only exhausted output-limit leaves, at most to the saved depth."""
    from .audio_output_limit_recovery_summary import output_limit_recovery_action
    policy = state.audio_output_limit_policy
    parent = state.slots[slot_index]
    children = []
    history = parent.output_limit_evidence
    changed = False
    for candidate in parent.subslots or (parent,):
        if output_limit_recovery_action(candidate, policy) != 'bisect':
            children.append(candidate)
            continue
        midpoint = (candidate.logical_start_seconds + candidate.logical_end_seconds) / 2
        if not candidate.logical_start_seconds < midpoint < candidate.logical_end_seconds:
            children.append(candidate)
            continue
        for start, end in ((candidate.logical_start_seconds, midpoint),
                           (midpoint, candidate.logical_end_seconds)):
            children.append(MergedAudioSlot(
                index=len(children), logical_start_seconds=start, logical_end_seconds=end,
                actual_start_seconds=(candidate.actual_start_seconds
                                      if start == candidate.logical_start_seconds else start),
                actual_end_seconds=(candidate.actual_end_seconds
                                    if end == candidate.logical_end_seconds else end),
                split_depth=candidate.split_depth + 1,
            ))
        if parent.subslots:
            history += candidate.output_limit_evidence
        changed = True
    if not changed:
        return state
    slots = list(state.slots)
    slots[slot_index] = replace(parent, output_limit_evidence=history,
                               subslots=tuple(replace(child, index=index)
                                              for index, child in enumerate(children)))
    return replace(state, slots=tuple(slots))
