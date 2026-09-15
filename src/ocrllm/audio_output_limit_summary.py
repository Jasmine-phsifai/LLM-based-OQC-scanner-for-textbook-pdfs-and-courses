"""Expose small, durable ASR recovery facts without checkpoint consumers."""
from dataclasses import asdict
from .is_audio_generation_failure import is_generation_repetition_failure
from .audio_output_limit_recovery_summary import output_limit_recovery_action


def audio_output_limit_summary(state):
    leaves = [leaf for parent in state.slots for leaf in parent.subslots or (parent,)]
    return {
        'audio_output_limit_policy': asdict(state.audio_output_limit_policy),
        'output_limit_failure_evidence': [
            row for parent in state.slots for slot in (parent, *parent.subslots)
            for row in slot.output_limit_evidence
        ],
        'output_limit_exhausted_segments': [
            {'start_seconds': leaf.logical_start_seconds, 'end_seconds': leaf.logical_end_seconds,
             'split_depth': leaf.split_depth, 'attempts_reserved': leaf.recovery_attempts,
             'confirmed_consecutive_output_limits': leaf.output_limit_attempts,
             'status': leaf.status}
            for leaf in leaves if leaf.status != 'settled'
            and (leaf.recovery_attempts >= 1 + state.audio_output_limit_policy.max_retries
                 or (is_generation_repetition_failure(leaf)
                     and output_limit_recovery_action(leaf, state.audio_output_limit_policy) is None))
        ],
    }
