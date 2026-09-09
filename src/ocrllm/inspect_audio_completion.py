"""Read audio completion and actual failed ranges through an owner public API."""
from pathlib import Path
from .audio_gap_policy import AudioGapPolicy


def inspect_audio_completion(output_path: str | Path, *, audio_gap_policy: AudioGapPolicy | None = None) -> dict:
    """Summarize durable audio state without inference or mutation.

    A supplied policy evaluates threshold eligibility without changing the saved
    completion decision. A completed file without state has unknown gap details.
    Use only for caller-owned OCRLLM merged-audio targets.
    """
    from .audio_gap_summary import audio_gap_summary
    from .output.resolve_resume_state_path import resolve_resume_state_path
    from .output.load_merged_audio_resume_state import load_merged_audio_resume_state
    from .errors import ConfigError
    if audio_gap_policy is not None and type(audio_gap_policy) is not AudioGapPolicy:
        raise ConfigError('audio_gap_policy must be an AudioGapPolicy.', code='CONFIG_INVALID')
    path = Path(output_path)
    state_path = resolve_resume_state_path(path)
    if not state_path.exists():
        return {'status': 'complete' if path.is_file() else 'missing',
                'failed_seconds': None, 'failed_fraction': None, 'failed_segments': None,
                'accepted_with_gaps': False}
    state = load_merged_audio_resume_state(state_path)
    summary = audio_gap_summary(state, audio_gap_policy)
    summary['would_accept_with_supplied_policy'] = summary['accepted_with_gaps']
    summary['accepted_with_gaps'] = state.accepted_with_gaps
    summary['status'] = ('complete_with_gaps' if state.accepted_with_gaps and path.is_file() else 'partial')
    return summary
