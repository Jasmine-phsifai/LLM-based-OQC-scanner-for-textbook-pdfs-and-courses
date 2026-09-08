"""Provide the explicitly selected bounded transient retry recipe."""


def bounded_transient_retry_rules() -> dict[str, tuple[str, int, int]]:
    """Return one retry after two seconds for canonical transient failures.

    This is an opt-in recipe; ProviderModel defaults and permanent request,
    authentication, format and output-validation errors remain unchanged.
    """
    return {code: ('current', 1, 2) for code in (
        'PROVIDER_RATE_LIMITED', 'PROVIDER_UNAVAILABLE', 'PROVIDER_TIMEOUT',
    )}
