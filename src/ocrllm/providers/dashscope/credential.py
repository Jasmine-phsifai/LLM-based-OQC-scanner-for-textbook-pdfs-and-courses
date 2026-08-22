"""One labeled secret DashScope credential for runtime scheduling."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ...errors import ConfigError
from .validate_dashscope_api_key import validate_dashscope_api_key


_CREDENTIAL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


@dataclass(frozen=True, slots=True)
class DashScopeCredential:
    """Bind a non-secret operational ID to one secret API key."""

    credential_id: str
    api_key: str = field(repr=False)

    def __post_init__(self) -> None:
        if (
            type(self.credential_id) is not str
            or _CREDENTIAL_ID.fullmatch(self.credential_id) is None
        ):
            raise ConfigError(
                "DashScopeCredential.credential_id must be 1-64 safe ID characters.",
                code="CONFIG_INVALID",
            ) from None
        validate_dashscope_api_key(
            self.api_key,
            field_name="DashScopeCredential.api_key",
        )
