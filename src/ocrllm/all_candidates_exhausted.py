"""Terminating error for an exhausted caller-supplied model chain."""

from __future__ import annotations

from .errors import QuotaExhausted


class AllCandidatesExhausted(QuotaExhausted):
    """Every configured model failed with a model-serving disposition."""

    default_message = "All configured provider model candidates are exhausted."
