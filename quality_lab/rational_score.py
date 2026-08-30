"""Represent quality counts without binary floating-point comparisons."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RationalScore:
    """An exact, bounded numerator and denominator."""

    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if type(self.numerator) is not int or type(self.denominator) is not int:
            raise TypeError("rational score counts must be exact integers")
        if self.denominator <= 0:
            raise ValueError("rational score denominator must be positive")
        if not 0 <= self.numerator <= self.denominator:
            raise ValueError("rational score numerator must be within its denominator")

    def meets(self, threshold: "RationalScore") -> bool:
        """Compare two fractions using integer cross multiplication."""

        if not isinstance(threshold, RationalScore):
            raise TypeError("threshold must be a RationalScore")
        return self.numerator * threshold.denominator >= (
            self.denominator * threshold.numerator
        )


ZERO_SCORE = RationalScore(0, 1)
PERFECT_SCORE = RationalScore(1, 1)
