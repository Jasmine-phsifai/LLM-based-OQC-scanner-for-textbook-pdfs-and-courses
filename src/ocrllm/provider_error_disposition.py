"""Convert one stable provider error into pool-facing policy evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from .errors import ProviderError


ProviderFailureAction = Literal[
    "retry",
    "cooldown",
    "quarantine_credential",
    "stop",
    "fix_request",
    "change_source",
    "inspect_response",
]
ProviderFailureScope = Literal[
    "request",
    "credential",
    "model",
    "account",
    "provider",
]

_ACTIONS = frozenset(
    {
        "retry",
        "cooldown",
        "quarantine_credential",
        "stop",
        "fix_request",
        "change_source",
        "inspect_response",
    }
)
_SCOPES = frozenset({"request", "credential", "model", "account", "provider"})
_DEFAULT_BY_CODE: dict[str, tuple[ProviderFailureAction, ProviderFailureScope]] = {
    "PROVIDER_AUTHENTICATION": ("quarantine_credential", "credential"),
    "PROVIDER_PERMISSION_DENIED": ("quarantine_credential", "credential"),
    "PROVIDER_ACCOUNT_SUSPENDED": ("stop", "account"),
    "PROVIDER_RATE_LIMITED": ("cooldown", "provider"),
    "PROVIDER_CONCURRENCY_LIMITED": ("cooldown", "provider"),
    "PROVIDER_QUOTA_EXHAUSTED": ("stop", "account"),
    "PROVIDER_TIMEOUT": ("retry", "provider"),
    "PROVIDER_NETWORK": ("retry", "provider"),
    "PROVIDER_UNAVAILABLE": ("retry", "provider"),
    "PROVIDER_CATALOG_UNAVAILABLE": ("retry", "provider"),
    "PROVIDER_REQUEST_INVALID": ("fix_request", "request"),
    "PROVIDER_CONTENT_BLOCKED": ("change_source", "request"),
    "PROVIDER_RESPONSE_INVALID": ("inspect_response", "request"),
    # A refusal is the model declining a well-formed request: the source is what
    # must change, not the request shape or the credential.
    "PROVIDER_REFUSED_RECOGNITION": ("change_source", "request"),
}


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderErrorDisposition:
    """Describe what later runtime policy may do with one provider failure."""

    action: ProviderFailureAction
    scope: ProviderFailureScope
    retryable: bool

    def __post_init__(self) -> None:
        if type(self.action) is not str or self.action not in _ACTIONS:
            raise ValueError("provider failure action is not canonical") from None
        if type(self.scope) is not str or self.scope not in _SCOPES:
            raise ValueError("provider failure scope is not canonical") from None
        if type(self.retryable) is not bool:
            raise TypeError("provider failure retryable must be a boolean") from None


def get_provider_error_disposition(error: ProviderError) -> ProviderErrorDisposition:
    """Return immutable action/scope evidence without performing the action."""
    if not isinstance(error, ProviderError):
        raise TypeError("error must be a ProviderError") from None
    try:
        action, default_scope = _DEFAULT_BY_CODE[error.code]
    except KeyError:
        raise ValueError("provider error code has no disposition") from None

    configured_scope = error.details.get("failure_scope")
    scope = (
        cast(ProviderFailureScope, configured_scope)
        if type(configured_scope) is str and configured_scope in _SCOPES
        else default_scope
    )
    return ProviderErrorDisposition(
        action=action,
        scope=scope,
        retryable=error.retryable,
    )
