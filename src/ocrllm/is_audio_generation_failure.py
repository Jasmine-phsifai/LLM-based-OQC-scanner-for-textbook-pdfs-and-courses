"""Recognize explicit provider generation failures for bounded audio recovery."""
import re
from .audio_gap_summary import is_output_limit_failure

_REPETITION = re.compile(
    r" \[provider_code=generation_repetition(?: request_id=[A-Za-z0-9][A-Za-z0-9._:-]{0,127})?\]$"
)


def is_generation_repetition_failure(slot):
    return (slot.status == 'failed' and slot.error_code == 'PROVIDER_REQUEST_INVALID'
            and _REPETITION.search(slot.error_description or '') is not None)


def is_audio_generation_failure(slot):
    # Gap acceptance deliberately continues to require output-limit evidence.
    return is_output_limit_failure(slot) or is_generation_repetition_failure(slot)
