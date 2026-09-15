"""Inspect available cap recovery without dispatching or changing checkpoints."""
from dataclasses import asdict

from .is_audio_generation_failure import is_audio_generation_failure, is_generation_repetition_failure


def output_limit_recovery_action(slot, policy):
    """Use the same narrow classification for recovery planning and inspection."""
    if not is_audio_generation_failure(slot):
        return None
    if not is_generation_repetition_failure(slot) and slot.recovery_attempts < 1 + policy.max_retries:
        return 'retry'
    midpoint = (slot.logical_start_seconds + slot.logical_end_seconds) / 2
    if (slot.split_depth < policy.max_split_depth
        and slot.logical_start_seconds < midpoint < slot.logical_end_seconds):
        return 'bisect'
    return None


def audio_output_limit_recovery_summary(state, policy=None, *, publication_pending=False):
    """Evaluate a requested policy in memory, respecting saved terminal budgets."""
    selected = policy or state.audio_output_limit_policy
    mismatch = bool(state.audio_output_limit_policy and selected != state.audio_output_limit_policy)
    summary = {
        'output_limit_recovery_policy': asdict(selected) if selected else None,
        'output_limit_recovery_policy_mismatch': mismatch,
        'output_limit_recovery_from_legacy': state.audio_output_limit_policy is None,
        'audio_publication_pending': publication_pending,
        'output_limit_recovery_available': publication_pending,
        'output_limit_recovery_candidate_seconds': 0.0,
        'output_limit_recovery_candidates': [],
    }
    if selected is None or mismatch or state.accepted_with_gaps:
        return summary
    from .bisect_failed_audio_slots import upgrade_audio_output_limit_state
    evaluated = upgrade_audio_output_limit_state(state, selected)
    candidates = summary['output_limit_recovery_candidates']
    for parent in evaluated.slots:
        for leaf in parent.subslots or (parent,):
            remaining = max(0, 1 + selected.max_retries - leaf.recovery_attempts)
            action = output_limit_recovery_action(leaf, selected)
            if (leaf.status == 'unresolved' and leaf.split_depth > 0 and remaining
                and _has_ancestor_cap_evidence(parent, leaf)):
                action = 'continue'
            if action is not None:
                candidates.append({
                    'start_seconds': leaf.logical_start_seconds, 'end_seconds': leaf.logical_end_seconds,
                    'action': action, 'split_depth': leaf.split_depth, 'attempts_remaining': remaining,
                })
    summary['output_limit_recovery_available'] = publication_pending or bool(candidates)
    summary['output_limit_recovery_candidate_seconds'] = sum(
        row['end_seconds'] - row['start_seconds'] for row in candidates
    )
    return summary


def _has_ancestor_cap_evidence(parent, leaf):
    # These records are written only for confirmed generation failures. An old aggregate
    # parent's latest error may instead belong to a child, so it is not evidence.
    for row in parent.output_limit_evidence:
        start, end, depth = row.get('start_seconds'), row.get('end_seconds'), row.get('split_depth')
        if (type(start) in (int, float) and type(end) in (int, float) and type(depth) is int
            and depth < leaf.split_depth
            and start <= leaf.logical_start_seconds < leaf.logical_end_seconds <= end):
            return True
    return False
