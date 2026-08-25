"""Immutable internal output shared by recognition processors."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping

from .freeze_json_value import JSONValue, freeze_json_value


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcessorOutput:
    """A processor result before optional final-output writing."""

    media_type: Literal["image", "pdf", "audio", "video"]
    markdown: str
    profile: str | None = None
    status: Literal["complete", "partial"] = "complete"
    assets: tuple[Path, ...] = ()
    hotwords: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.markdown, str) or not self.markdown.strip():
            raise ValueError("ProcessorOutput.markdown must contain text")
        if self.media_type not in {"image", "pdf", "audio", "video"}:
            raise ValueError("ProcessorOutput.media_type is not a canonical media type")
        if self.profile is not None and (
            not isinstance(self.profile, str) or not self.profile.strip()
        ):
            raise ValueError("ProcessorOutput.profile must be nonempty text when set")
        if self.status not in {"complete", "partial"}:
            raise ValueError("ProcessorOutput.status must be 'complete' or 'partial'")
        hotwords = tuple(self.hotwords)
        warnings = tuple(self.warnings)
        if any(not isinstance(value, str) for value in hotwords):
            raise TypeError("ProcessorOutput.hotwords must contain only text")
        if any(not isinstance(value, str) for value in warnings):
            raise TypeError("ProcessorOutput.warnings must contain only text")

        frozen_metadata = freeze_json_value(self.metadata)
        if not isinstance(frozen_metadata, MappingProxyType):
            raise TypeError("ProcessorOutput.metadata must be a JSON object")

        object.__setattr__(self, "assets", tuple(Path(path) for path in self.assets))
        object.__setattr__(self, "hotwords", hotwords)
        object.__setattr__(self, "warnings", warnings)
        object.__setattr__(self, "metadata", frozen_metadata)
