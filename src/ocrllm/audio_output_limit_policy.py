"""Explicit, finite recovery of provider-reported audio output limits."""
from dataclasses import dataclass

from .errors import ConfigError


@dataclass(frozen=True, slots=True, kw_only=True)
class AudioOutputLimitPolicy:
    """Bound attempts per range and binary subdivisions of its source interval.

    The initial request is separate from max_retries. Interrupted dispatched
    attempts consume budget; they do not prove an output-limit failure.
    Explicit generation_repetition failures bisect without identical retries,
    within max_split_depth. They never qualify as accepted short audio gaps.
    """

    max_retries: int = 2
    max_split_depth: int = 2

    def __post_init__(self):
        for name in ('max_retries', 'max_split_depth'):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= 2:
                raise ConfigError(f'{name} must be an integer from 0 to 2.', code='CONFIG_INVALID')
