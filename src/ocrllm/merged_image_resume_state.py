"""Strict schema for one merged-image recognition sidecar."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from .contracts.source_fingerprint import SourceFingerprint
from .errors import ResumeStateError
from .provider_model_usage import ProviderModelUsage


MERGED_IMAGE_RESUME_STATE_VERSION = "ocrllm.merged-image-resume.v1"
_IMAGE_TASKS = frozenset({"plain_ocr", "detail_ocr"})
_SLOT_STATUSES = frozenset({"unresolved", "settled", "failed"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ROOT_KEYS = frozenset(
    {
        "state_version",
        "image_task",
        "prompt_version",
        "sources",
        "slots",
        "usage",
        "provider_cleanup_failed",
    }
)
_SOURCE_KEYS = frozenset({"uri", "byte_size", "sha256"})
_SLOT_KEYS = frozenset(
    {
        "index",
        "source_indexes",
        "status",
        "markdown",
        "markdown_sha256",
        "vendor",
        "model",
        "error_code",
        "error_description",
    }
)
_USAGE_KEYS = frozenset(
    {"vendor", "model", "calls", "input_tokens", "output_tokens"}
)


@dataclass(frozen=True, slots=True, kw_only=True)
class MergedImageSlot:
    """Store one immutable image group and its latest settled outcome."""

    index: int
    source_indexes: tuple[int, ...]
    status: str = "unresolved"
    markdown: str | None = None
    markdown_sha256: str | None = None
    vendor: str | None = None
    model: str | None = None
    error_code: str | None = None
    error_description: str | None = None

    def __post_init__(self) -> None:
        if type(self.index) is not int or self.index < 0:
            raise ValueError("merged-image slot index is invalid")
        if (
            type(self.source_indexes) is not tuple
            or not self.source_indexes
            or any(type(value) is not int or value < 0 for value in self.source_indexes)
            or tuple(sorted(self.source_indexes)) != self.source_indexes
            or len(set(self.source_indexes)) != len(self.source_indexes)
        ):
            raise ValueError("merged-image slot source indexes are invalid")
        if type(self.status) is not str or self.status not in _SLOT_STATUSES:
            raise ValueError("merged-image slot status is invalid")
        if self.status == "settled":
            if (
                type(self.markdown) is not str
                or not self.markdown.strip()
                or type(self.markdown_sha256) is not str
                or _SHA256.fullmatch(self.markdown_sha256) is None
                or self.markdown_sha256
                != hashlib.sha256(self.markdown.encode("utf-8")).hexdigest()
                or not _is_text(self.vendor)
                or not _is_text(self.model)
                or self.error_code is not None
                or self.error_description is not None
            ):
                raise ValueError("settled merged-image slot is invalid")
        elif self.status == "failed":
            if (
                self.markdown is not None
                or self.markdown_sha256 is not None
                or not _is_text(self.vendor)
                or not _is_text(self.model)
                or not _is_text(self.error_code)
                or not _is_text(self.error_description)
            ):
                raise ValueError("failed merged-image slot is invalid")
        elif any(
            value is not None
            for value in (
                self.markdown,
                self.markdown_sha256,
                self.vendor,
                self.model,
                self.error_code,
                self.error_description,
            )
        ):
            raise ValueError("unresolved merged-image slot carries outcome data")


@dataclass(frozen=True, slots=True, kw_only=True)
class MergedImageResumeState:
    """Store one fixed merged-image plan and every reusable slot outcome."""

    state_version: str
    image_task: str
    prompt_version: str
    sources: tuple[SourceFingerprint, ...]
    slots: tuple[MergedImageSlot, ...]
    usage: tuple[ProviderModelUsage, ...] = ()
    provider_cleanup_failed: bool = False

    def __post_init__(self) -> None:
        if self.state_version != MERGED_IMAGE_RESUME_STATE_VERSION:
            raise ValueError("merged-image resume state version is unsupported")
        if type(self.image_task) is not str or self.image_task not in _IMAGE_TASKS:
            raise ValueError("merged-image task is invalid")
        if not _is_text(self.prompt_version):
            raise ValueError("merged-image prompt version is invalid")
        if (
            type(self.sources) is not tuple
            or not self.sources
            or any(type(value) is not SourceFingerprint for value in self.sources)
        ):
            raise ValueError("merged-image sources are invalid")
        if (
            type(self.slots) is not tuple
            or not self.slots
            or any(type(value) is not MergedImageSlot for value in self.slots)
            or tuple(slot.index for slot in self.slots) != tuple(range(len(self.slots)))
        ):
            raise ValueError("merged-image slots are invalid")
        planned_sources = tuple(
            source_index for slot in self.slots for source_index in slot.source_indexes
        )
        if planned_sources != tuple(range(len(self.sources))):
            raise ValueError("merged-image slot membership is invalid")
        if (
            type(self.usage) is not tuple
            or any(type(value) is not ProviderModelUsage for value in self.usage)
            or len({(value.vendor, value.model) for value in self.usage})
            != len(self.usage)
        ):
            raise ValueError("merged-image usage rows are invalid")
        if type(self.provider_cleanup_failed) is not bool:
            raise ValueError("merged-image cleanup state is invalid")

    def to_bytes(self) -> bytes:
        """Return deterministic secret-free UTF-8 JSON."""
        document = {
            "state_version": self.state_version,
            "image_task": self.image_task,
            "prompt_version": self.prompt_version,
            "sources": [
                {
                    "uri": source.uri,
                    "byte_size": source.byte_size,
                    "sha256": source.sha256,
                }
                for source in self.sources
            ],
            "slots": [
                {
                    "index": slot.index,
                    "source_indexes": list(slot.source_indexes),
                    "status": slot.status,
                    "markdown": slot.markdown,
                    "markdown_sha256": slot.markdown_sha256,
                    "vendor": slot.vendor,
                    "model": slot.model,
                    "error_code": slot.error_code,
                    "error_description": slot.error_description,
                }
                for slot in self.slots
            ],
            "usage": [
                {
                    "vendor": row.vendor,
                    "model": row.model,
                    "calls": row.calls,
                    "input_tokens": row.input_tokens,
                    "output_tokens": row.output_tokens,
                }
                for row in self.usage
            ],
            "provider_cleanup_failed": self.provider_cleanup_failed,
        }
        return (
            json.dumps(
                document,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")

    @classmethod
    def from_bytes(cls, raw: bytes) -> MergedImageResumeState:
        """Reject duplicate keys, schema drift, and invalid slot content."""
        try:
            if type(raw) is not bytes:
                raise ValueError
            document = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
            return _state_from_document(document)
        except ResumeStateError:
            raise
        except Exception:
            raise ResumeStateError(
                "The merged-image resume state is corrupt or unsupported.",
                code="RESUME_STATE_INVALID",
            ) from None


def _state_from_document(document: object) -> MergedImageResumeState:
    if type(document) is not dict or frozenset(document) != _ROOT_KEYS:
        raise ValueError
    source_documents = document["sources"]
    slot_documents = document["slots"]
    usage_documents = document["usage"]
    if (
        type(source_documents) is not list
        or type(slot_documents) is not list
        or type(usage_documents) is not list
    ):
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
        source_indexes = slot["source_indexes"]
        if type(source_indexes) is not list:
            raise ValueError
        slots.append(
            MergedImageSlot(
                index=slot["index"],
                source_indexes=tuple(source_indexes),
                status=slot["status"],
                markdown=slot["markdown"],
                markdown_sha256=slot["markdown_sha256"],
                vendor=slot["vendor"],
                model=slot["model"],
                error_code=slot["error_code"],
                error_description=slot["error_description"],
            )
        )
    usage = []
    for row in usage_documents:
        if type(row) is not dict or frozenset(row) != _USAGE_KEYS:
            raise ValueError
        usage.append(
            ProviderModelUsage(
                vendor=row["vendor"],
                model=row["model"],
                calls=row["calls"],
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
            )
        )
    return MergedImageResumeState(
        state_version=document["state_version"],
        image_task=document["image_task"],
        prompt_version=document["prompt_version"],
        sources=tuple(sources),
        slots=tuple(slots),
        usage=tuple(usage),
        provider_cleanup_failed=document["provider_cleanup_failed"],
    )


def _is_text(value: object) -> bool:
    return type(value) is str and bool(value.strip())


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _reject_constant(_value: str) -> object:
    raise ValueError
