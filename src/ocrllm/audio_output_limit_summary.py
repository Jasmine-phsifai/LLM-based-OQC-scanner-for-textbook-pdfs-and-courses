"""Expose small, durable ASR recovery facts without checkpoint consumers."""
from dataclasses import asdict
from .audio_gap_summary import is_output_limit_evidence, is_output_limit_failure
from .is_audio_generation_failure import is_generation_repetition_failure


def audio_output_limit_summary(state):
    leaves = [leaf for parent in state.slots for leaf in parent.subslots or (parent,)]
    evidence = [row for parent in state.slots for slot in (parent, *parent.subslots)
                for row in slot.output_limit_evidence]
    maximum = 1 + state.audio_output_limit_policy.max_retries
    return {
        'audio_output_limit_policy': asdict(state.audio_output_limit_policy),
        'output_limit_failure_evidence': [row for row in evidence if is_output_limit_evidence(row)],
        'generation_repetition_failure_evidence': [
            row for row in evidence if row.get('provider_code') == 'generation_repetition'],
        'generation_repetition_failed_segments': [
            {'start_seconds': leaf.logical_start_seconds, 'end_seconds': leaf.logical_end_seconds,
             'split_depth': leaf.split_depth, 'attempts_reserved': leaf.recovery_attempts,
             'attempts_remaining': max(0, maximum - leaf.recovery_attempts),
             'retry_exhausted': leaf.recovery_attempts >= maximum, 'status': leaf.status}
            for leaf in leaves if is_generation_repetition_failure(leaf)],
        'output_limit_exhausted_segments': [
            {'start_seconds': leaf.logical_start_seconds, 'end_seconds': leaf.logical_end_seconds,
             'split_depth': leaf.split_depth, 'attempts_reserved': leaf.recovery_attempts,
             'confirmed_consecutive_output_limits': leaf.output_limit_attempts,
             'status': leaf.status}
            for leaf in leaves if is_output_limit_failure(leaf)
            and leaf.recovery_attempts >= maximum
        ],
    }
