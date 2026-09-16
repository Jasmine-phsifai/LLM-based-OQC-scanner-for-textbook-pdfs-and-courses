"""Read audio completion and actual failed ranges through an owner public API."""
from pathlib import Path
from .audio_gap_policy import AudioGapPolicy
from .audio_output_limit_policy import AudioOutputLimitPolicy


def inspect_audio_completion(output_path: str | Path, *, audio_gap_policy: AudioGapPolicy | None = None,
                             audio_output_limit_policy: AudioOutputLimitPolicy | None = None) -> dict:
    """Summarize durable audio state without inference or mutation.

    A supplied policy evaluates threshold eligibility without changing the saved
    completion decision. A completed file without state has unknown gap details.
    audio_output_limit_policy evaluates only explicit token-cap recovery work without
    changing the saved policy, retry counts or publication. Candidate fields
    include pending derived ranges whose saved ancestor proves a token-cap failure.
    audio_dispatch_checkpoint_confirmed conservatively verifies the latest saved
    reservations of current v4 binary-policy leaves. It is only a snapshot:
    the caller must already prevent new dispatch through its decision, and must
    separately prove model-service idleness. False or an inspection error is
    not permission to stop a worker. See the owner safe-stop contract.
    Use only for caller-owned OCRLLM merged-audio targets.
    """
    from .audio_gap_summary import audio_gap_summary
    from .output.resolve_resume_state_path import resolve_resume_state_path
    from .output.load_merged_audio_resume_state import load_merged_audio_resume_state
    from .errors import ConfigError
    from .audio_dispatch_checkpoint_summary import audio_dispatch_checkpoint_summary
    if audio_gap_policy is not None and type(audio_gap_policy) is not AudioGapPolicy:
        raise ConfigError('audio_gap_policy must be an AudioGapPolicy.', code='CONFIG_INVALID')
    if audio_output_limit_policy is not None and type(audio_output_limit_policy) is not AudioOutputLimitPolicy:
        raise ConfigError('audio_output_limit_policy must be an AudioOutputLimitPolicy.', code='CONFIG_INVALID')
    path = Path(output_path)
    state_path = resolve_resume_state_path(path)
    if not state_path.exists():
        return {'status': 'complete' if path.is_file() else 'missing',
                'failed_seconds': None, 'failed_fraction': None, 'failed_segments': None,
                'accepted_with_gaps': False, 'audio_publication_pending': False, 'output_limit_recovery_available': False,
                'output_limit_recovery_candidate_seconds': 0.0, 'output_limit_recovery_candidates': [],
                **audio_dispatch_checkpoint_summary(None)}
    state = load_merged_audio_resume_state(state_path)
    summary = audio_gap_summary(state, audio_gap_policy)
    summary.update(audio_dispatch_checkpoint_summary(state))
    summary['would_accept_with_supplied_policy'] = summary['accepted_with_gaps']
    summary['accepted_with_gaps'] = state.accepted_with_gaps
    from .is_audio_markdown_published import is_audio_markdown_published
    published = is_audio_markdown_published(state, path)
    summary['status'] = ('complete_with_gaps' if state.accepted_with_gaps and published
                         else 'complete' if state.audio_output_limit_policy and published and all(slot.status == 'settled' for slot in state.slots)
                         else 'partial')
    if state.audio_output_limit_policy is not None:
        from .audio_output_limit_summary import audio_output_limit_summary
        summary.update(audio_output_limit_summary(state))
    from .audio_output_limit_recovery_summary import audio_output_limit_recovery_summary
    publication_pending = summary['status'] == 'partial' and (
        state.accepted_with_gaps or all(slot.status == 'settled' for slot in state.slots)
    )
    summary.update(audio_output_limit_recovery_summary(
        state, audio_output_limit_policy, publication_pending=publication_pending,
    ))
    return summary
