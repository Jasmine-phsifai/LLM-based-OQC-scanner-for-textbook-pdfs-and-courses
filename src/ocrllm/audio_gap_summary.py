"""Summarize actual audio leaves without counting failed parents twice."""
import re


_OUTPUT_LIMIT_DIAGNOSTIC = re.compile(
    r" \[provider_code=output_token_limit(?: request_id=[A-Za-z0-9][A-Za-z0-9._:-]{0,127})?\]$"
)


def is_output_limit_failure(slot):
    description = slot.error_description or ''
    return (slot.status == 'failed' and slot.error_code == 'PROVIDER_REQUEST_INVALID'
            and _OUTPUT_LIMIT_DIAGNOSTIC.search(description) is not None)


def is_output_limit_evidence(row):
    """Distinguish cap evidence from loop records in the unchanged v4 field."""
    code = row.get('provider_code')
    if code is not None:
        return code == 'output_token_limit'
    # Before provider_code was persisted, adoption saved the canonical error
    # description. A mention inside free prose is still not cap evidence.
    description = row.get('description')
    return (isinstance(description, str)
            and _OUTPUT_LIMIT_DIAGNOSTIC.search(description) is not None)


def audio_gap_summary(state, policy=None):
    policy = policy if policy is not None else state.audio_gap_policy
    failed = []
    pending = 0
    for parent in state.slots:
        for leaf in parent.subslots or (parent,):
            if leaf.status == 'unresolved':
                pending += 1
            elif leaf.status == 'failed':
                failed.append({
                    'slot_index': parent.index,
                    'subslot_index': leaf.index if parent.subslots else None,
                    'start_seconds': leaf.logical_start_seconds,
                    'end_seconds': leaf.logical_end_seconds,
                    'code': leaf.error_code, 'description': leaf.error_description,
                    'output_token_limit': is_output_limit_failure(leaf),
                    'output_limit_attempts': leaf.output_limit_attempts,
                })
    duration = state.slots[-1].logical_end_seconds
    seconds = sum(row['end_seconds']-row['start_seconds'] for row in failed)
    fraction = seconds / duration
    eligible = bool(failed) and not pending and all(row['output_token_limit'] for row in failed)
    threshold_met = bool(policy is not None and eligible
        and fraction <= policy.max_failed_fraction
        and all(row['end_seconds']-row['start_seconds'] <= policy.max_failed_segment_seconds for row in failed)
        and (policy.max_failed_seconds is None or seconds <= policy.max_failed_seconds))
    sufficient = eligible and all(row['output_limit_attempts'] >= 3 for row in failed)
    return {'failed_seconds': seconds, 'failed_fraction': fraction,
            'failed_segments': failed, 'unresolved_segment_count': pending,
            'gap_threshold_met': threshold_met,
            'gap_retry_evidence_sufficient': sufficient,
            'accepted_with_gaps': threshold_met and sufficient}
