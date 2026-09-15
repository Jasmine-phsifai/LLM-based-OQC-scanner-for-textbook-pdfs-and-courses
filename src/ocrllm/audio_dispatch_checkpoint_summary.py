"""Conservatively verify latest ASR reservations from one saved checkpoint."""

from .is_audio_generation_failure import is_audio_generation_failure
from .merged_audio_resume_state import BOUNDED_AUDIO_RESUME_STATE_VERSION


def audio_dispatch_checkpoint_summary(state):
    """A snapshot assertion, never a lock or proof that a model service is idle.

    The caller must already prevent every new dispatch and keep that barrier
    through its decision. Only the current v4 binary-policy format is supported.
    Historical ancestors no longer dispatch; inspect their current leaves only.
    """
    reason = 'confirmed'
    if state is None:
        reason = 'missing_state'
    elif (state.state_version != BOUNDED_AUDIO_RESUME_STATE_VERSION
          or state.audio_output_limit_policy is None):
        reason = 'unsupported_state'
    else:
        for parent in state.slots:
            for leaf in parent.subslots or (parent,):
                if leaf.status == 'settled':
                    continue
                if leaf.status == 'unresolved' and leaf.recovery_attempts == 0:
                    continue
                if not is_audio_generation_failure(leaf):
                    reason = ('unconfirmed_reservation' if leaf.status == 'unresolved'
                              else 'unverifiable_outcome')
                    break
                confirmed = any(
                    type(row.get('attempt')) is int
                    and row['attempt'] == leaf.recovery_attempts > 0
                    and type(row.get('split_depth')) is int
                    and row['split_depth'] == leaf.split_depth
                    and type(row.get('start_seconds')) in (int, float)
                    and type(row.get('end_seconds')) in (int, float)
                    and row['start_seconds'] == leaf.logical_start_seconds
                    and row['end_seconds'] == leaf.logical_end_seconds
                    and row.get('historical_attempts_unknown', False) is False
                    for row in leaf.output_limit_evidence
                )
                if not confirmed:
                    reason = 'unconfirmed_reservation'
                    break
            if reason != 'confirmed':
                break
    return {'audio_dispatch_checkpoint_confirmed': reason == 'confirmed',
            'audio_dispatch_checkpoint_reason': reason}
