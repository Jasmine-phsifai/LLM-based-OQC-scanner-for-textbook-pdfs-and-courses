"""Immutable routing and quality settings for the built-in DashScope provider."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from ...errors import ConfigError
from .resolve_dashscope_model import DEFAULT_DASHSCOPE_MODEL
from .supported_regions import SUPPORTED_DASHSCOPE_REGIONS
from .validate_dashscope_api_key import validate_dashscope_api_key

if TYPE_CHECKING:
    from .credential_pool import DashScopeCredentialPool


_OPENAI_COMPATIBLE_PATH = "/compatible-mode/v1"
_WORKSPACE_REGIONS = frozenset(
    {
        "ap-northeast-1",
        "ap-southeast-1",
        "cn-beijing",
        "cn-hongkong",
        "eu-central-1",
    }
)
_SHARED_HOST_BY_REGION = {
    "ap-southeast-1": "dashscope-intl.aliyuncs.com",
    "cn-beijing": "dashscope.aliyuncs.com",
    "cn-hongkong": "cn-hongkong.dashscope.aliyuncs.com",
    "us-east-1": "dashscope-us.aliyuncs.com",
}
_WORKSPACE_ID = re.compile(
    r"(?!trial$)(?!token-plan$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
)


@dataclass(frozen=True, slots=True)
class DashScopeSettings:
    """Explicit DashScope region, endpoint, and evidence-affecting options."""

    region: str
    base_url: str
    api_key: str | None = field(default=None, repr=False)
    credential_pool: DashScopeCredentialPool | None = field(default=None, repr=False)
    enable_thinking: bool = False
    vl_high_resolution_images: bool = True
    standalone_sign_scout_model: str | None = None

    @classmethod
    def for_region(
        cls,
        region: str,
        *,
        api_key: str | None = None,
        credential_pool: DashScopeCredentialPool | None = None,
        enable_thinking: bool = False,
        vl_high_resolution_images: bool = True,
        standalone_sign_scout_model: str | None = None,
    ) -> DashScopeSettings:
        """Create settings for a region that has a shared DashScope endpoint."""
        _validate_region(region)
        host = _SHARED_HOST_BY_REGION.get(region)
        if host is None:
            raise ConfigError(
                "DashScopeSettings.for_region requires a region with a shared endpoint."
            ) from None
        return cls(
            region=region,
            base_url=f"https://{host}{_OPENAI_COMPATIBLE_PATH}",
            api_key=api_key,
            credential_pool=credential_pool,
            enable_thinking=enable_thinking,
            vl_high_resolution_images=vl_high_resolution_images,
            standalone_sign_scout_model=standalone_sign_scout_model,
        )

    def __post_init__(self) -> None:
        _validate_region(self.region)
        _validate_base_url(self.base_url, region=self.region)
        if self.api_key is not None:
            validate_dashscope_api_key(
                self.api_key,
                field_name="DashScopeSettings.api_key",
            )
        _validate_credential_pool(
            self.credential_pool,
            api_key=self.api_key,
            region=self.region,
        )
        _require_exact_boolean(self.enable_thinking, field_name="enable_thinking")
        _require_exact_boolean(
            self.vl_high_resolution_images,
            field_name="vl_high_resolution_images",
        )
        scout_model = self.standalone_sign_scout_model
        if scout_model is not None and (
            type(scout_model) is not str
            or scout_model not in {"qwen-vl-max", DEFAULT_DASHSCOPE_MODEL}
        ):
            raise ConfigError(
                "DashScopeSettings.standalone_sign_scout_model must be None or "
                "one fixed supported scout model."
            ) from None


def _validate_region(region: object) -> None:
    if type(region) is not str or region not in SUPPORTED_DASHSCOPE_REGIONS:
        raise ConfigError(
            "DashScopeSettings.region must be a supported canonical region ID."
        ) from None


def _validate_credential_pool(
    pool: object | None,
    *,
    api_key: str | None,
    region: str,
) -> None:
    if pool is None:
        return
    from .credential_pool import DashScopeCredentialPool

    if type(pool) is not DashScopeCredentialPool:
        raise ConfigError(
            "DashScopeSettings.credential_pool must be exact "
            "DashScopeCredentialPool.",
            code="CONFIG_INVALID",
        ) from None
    if api_key is not None:
        raise ConfigError(
            "DashScopeSettings.api_key and credential_pool are mutually exclusive.",
            code="CONFIG_INVALID",
        ) from None
    if pool.region != region:
        raise ConfigError(
            "DashScopeSettings and credential_pool regions must match.",
            code="CONFIG_INVALID",
        ) from None


def _validate_base_url(base_url: object, *, region: str) -> None:
    if (
        type(base_url) is not str
        or not base_url
        or base_url != base_url.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in base_url)
    ):
        raise _invalid_base_url()

    try:
        parsed = urlsplit(base_url)
        hostname = parsed.hostname
        port = parsed.port
    except (TypeError, ValueError):
        raise _invalid_base_url() from None

    if (
        parsed.scheme != "https"
        or hostname is None
        or parsed.netloc != hostname
        or port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != _OPENAI_COMPATIBLE_PATH
        or parsed.query
        or parsed.fragment
        or base_url != f"https://{hostname}{_OPENAI_COMPATIBLE_PATH}"
    ):
        raise _invalid_base_url()

    if hostname == _SHARED_HOST_BY_REGION.get(region):
        return
    if region not in _WORKSPACE_REGIONS:
        raise _invalid_region_pair()

    workspace_suffix = f".{region}.maas.aliyuncs.com"
    if not hostname.endswith(workspace_suffix):
        raise _invalid_region_pair()
    workspace_id = hostname[: -len(workspace_suffix)]
    if _WORKSPACE_ID.fullmatch(workspace_id) is None:
        raise _invalid_base_url()


def _require_exact_boolean(value: object, *, field_name: str) -> None:
    if type(value) is not bool:
        raise ConfigError(f"DashScopeSettings.{field_name} must be a boolean") from None


def _invalid_base_url() -> ConfigError:
    return ConfigError(
        "DashScopeSettings.base_url must be an approved HTTPS OpenAI-compatible "
        "DashScope endpoint."
    )


def _invalid_region_pair() -> ConfigError:
    return ConfigError(
        "DashScopeSettings.region and base_url must identify the same DashScope region."
    )
