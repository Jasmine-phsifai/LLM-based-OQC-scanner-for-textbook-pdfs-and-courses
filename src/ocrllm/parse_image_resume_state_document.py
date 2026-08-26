"""Parse one strict image resume state JSON document."""

from __future__ import annotations

from .contracts.source_fingerprint import SourceFingerprint
from .errors import ResumeStateError
from .image_resume_state import ImageResumeState
from .image_slot_state import ImageSlotState


_ROOT_KEYS = frozenset(
    {
        "state_version",
        "identity_version",
        "request_fingerprint",
        "processor_name",
        "processor_version",
        "sources",
        "slots",
        "result",
        "final_markdown_sha256",
    }
)
_SOURCE_KEYS = frozenset({"uri", "byte_size", "sha256"})
_SLOT_KEYS = frozenset(
    {
        "slot_id",
        "workflow_pass",
        "provider",
        "model",
        "markdown",
        "markdown_sha256",
        "provider_calls_attempted",
    }
)
_RESULT_KEYS = frozenset(
    {"markdown", "media_type", "profile", "status", "hotwords", "warnings", "metadata"}
)


def parse_image_resume_state_document(document: object) -> ImageResumeState:
    """Validate one decoded JSON object without a second encode/decode pass."""
    try:
        if type(document) is not dict or frozenset(document) != _ROOT_KEYS:
            raise ValueError
        source_documents = document["sources"]
        slot_documents = document["slots"]
        result = document["result"]
        if type(source_documents) is not list or not source_documents:
            raise ValueError
        if type(slot_documents) is not list:
            raise ValueError
        sources = []
        for source in source_documents:
            if type(source) is not dict or frozenset(source) != _SOURCE_KEYS:
                raise ValueError
            sources.append(
                SourceFingerprint(
                    uri=source["uri"],
                    byte_size=source["byte_size"],
                    sha256=source["sha256"],
                )
            )
        slots = []
        for slot in slot_documents:
            if type(slot) is not dict or frozenset(slot) != _SLOT_KEYS:
                raise ValueError
            slots.append(
                ImageSlotState(
                    slot_id=slot["slot_id"],
                    workflow_pass=slot["workflow_pass"],
                    provider=slot["provider"],
                    model=slot["model"],
                    markdown=slot["markdown"],
                    markdown_sha256=slot["markdown_sha256"],
                    provider_calls_attempted=slot["provider_calls_attempted"],
                )
            )
        final_markdown_sha256 = document["final_markdown_sha256"]
        if type(final_markdown_sha256) is not str:
            raise ValueError
        if type(result) is not dict or frozenset(result) != _RESULT_KEYS:
            raise ValueError
        hotwords = result["hotwords"]
        warnings = result["warnings"]
        if type(hotwords) is not list or type(warnings) is not list:
            raise ValueError
        return ImageResumeState(
            state_version=document["state_version"],
            identity_version=document["identity_version"],
            request_fingerprint=document["request_fingerprint"],
            processor_name=document["processor_name"],
            processor_version=document["processor_version"],
            sources=tuple(sources),
            markdown=result["markdown"],
            media_type=result["media_type"],
            profile=result["profile"],
            status=result["status"],
            hotwords=tuple(hotwords),
            warnings=tuple(warnings),
            metadata=result["metadata"],
            slots=tuple(slots),
            final_markdown_sha256=final_markdown_sha256,
        )
    except ResumeStateError:
        raise
    except Exception:
        raise ResumeStateError(
            "The image resume state is corrupt or has an unsupported schema.",
            code="RESUME_STATE_INVALID",
        ) from None
