"""Strictly parse one bounded image resume JSON document."""

from __future__ import annotations

import json

from .errors import ResumeStateError
from .fingerprint_image_request import IMAGE_REQUEST_IDENTITY_VERSION
from .image_resume_state import ImageResumeState
from .parse_image_resume_state_document import parse_image_resume_state_document


_LEGACY_V1_STATE_VERSION = "ocrllm.image-resume.v1"
_LEGACY_V1_IDENTITY_VERSION = "ocrllm.image-request.v1"


class _DuplicateKey(ValueError):
    pass


def parse_image_resume_state(raw: bytes) -> ImageResumeState:
    """Reject duplicate keys, schema drift, and invalid completed results."""
    try:
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        if type(document) is not dict:
            raise ValueError
        if (
            document.get("state_version") == _LEGACY_V1_STATE_VERSION
            and "identity_version" not in document
        ):
            raise _LegacyIdentityVersion
        return parse_image_resume_state_document(document)
    except _LegacyIdentityVersion:
        raise ResumeStateError(
            "The image resume state was written under identity "
            f"{_LEGACY_V1_IDENTITY_VERSION} and cannot be reused under "
            f"{IMAGE_REQUEST_IDENTITY_VERSION}.",
            code="RESUME_STATE_MISMATCH",
            details={
                "state_identity_version": _LEGACY_V1_IDENTITY_VERSION,
                "request_identity_version": IMAGE_REQUEST_IDENTITY_VERSION,
            },
        ) from None
    except ResumeStateError:
        raise
    except Exception:
        raise ResumeStateError(
            "The image resume state is corrupt or has an unsupported schema.",
            code="RESUME_STATE_INVALID",
        ) from None


class _LegacyIdentityVersion(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey
        result[key] = value
    return result


def _reject_constant(_value: str) -> object:
    raise ValueError
