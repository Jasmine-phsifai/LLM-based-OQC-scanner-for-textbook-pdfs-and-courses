"""Immutable direct-Python recognition result."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping

from .freeze_json_value import JSONValue, freeze_json_value


@dataclass(frozen=True, slots=True, kw_only=True)
class RecognitionResult:
    """Structured successful output from one recognition request."""

    markdown: str
    source_type: Literal["image", "pdf", "audio", "video"]
    profile: str | None = None
    status: Literal["complete", "partial"] = "complete"
    output_path: Path | None = None
    assets: tuple[Path, ...] = ()
    hotwords: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.markdown, str) or not self.markdown.strip():
            raise ValueError("RecognitionResult.markdown must contain text")
        if self.source_type not in {"image", "pdf", "audio", "video"}:
            raise ValueError("RecognitionResult.source_type is not a canonical media type")
        if self.profile is not None and (
            not isinstance(self.profile, str) or not self.profile.strip()
        ):
            raise ValueError("RecognitionResult.profile must be nonempty text when set")
        if self.status not in {"complete", "partial"}:
            raise ValueError("RecognitionResult.status must be 'complete' or 'partial'")
        hotwords = tuple(self.hotwords)
        warnings = tuple(self.warnings)
        if any(not isinstance(value, str) for value in hotwords):
            raise TypeError("RecognitionResult.hotwords must contain only text")
        if any(not isinstance(value, str) for value in warnings):
            raise TypeError("RecognitionResult.warnings must contain only text")

        frozen_metadata = freeze_json_value(self.metadata)
        if not isinstance(frozen_metadata, MappingProxyType):
            raise TypeError("RecognitionResult.metadata must be a JSON object")

        object.__setattr__(self, "output_path", Path(self.output_path) if self.output_path else None)
        object.__setattr__(self, "assets", tuple(Path(path) for path in self.assets))
        object.__setattr__(self, "hotwords", hotwords)
        object.__setattr__(self, "warnings", warnings)
        object.__setattr__(self, "metadata", frozen_metadata)
