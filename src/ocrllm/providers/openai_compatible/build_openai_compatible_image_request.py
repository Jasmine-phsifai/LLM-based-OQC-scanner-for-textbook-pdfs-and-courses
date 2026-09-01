"""Build one provider-neutral Chat Completions image request."""

from __future__ import annotations

import base64
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...errors import ConfigError, InvalidSource
from ...imaging.decode_image_bytes import decode_image_bytes
from ...validate_image_group import validate_image_group
from ...validate_source import MAX_SOURCE_BYTES, validate_source


_MIME_TYPE_BY_FORMAT = {"JPEG": "image/jpeg", "PNG": "image/png"}


@dataclass(frozen=True, slots=True, kw_only=True)
class OpenAICompatibleImageRequest:
    """Hold immutable request content without exposing encoded images in repr."""

    _model: str = field(repr=False)
    _prompt: str = field(repr=False)
    _data_urls: tuple[str, ...] = field(repr=False)

    @property
    def kwargs(self) -> dict[str, Any]:
        """Return fresh containers for one Chat Completions request."""
        return {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        *(
                            {"type": "image_url", "image_url": {"url": data_url}}
                            for data_url in self._data_urls
                        ),
                        {"type": "text", "text": self._prompt},
                    ],
                }
            ],
        }


def build_openai_compatible_image_request(
    image_paths: Sequence[Path],
    *,
    prompt: str,
    model: str,
) -> OpenAICompatibleImageRequest:
    """Validate ordered snapshots and encode standard image-url content."""
    if type(prompt) is not str or not prompt.strip():
        raise ConfigError(
            "OpenAI-compatible image recognition requires a nonempty prompt.",
            code="CONFIG_INVALID",
        ) from None
    if type(model) is not str or not model or model != model.strip():
        raise ConfigError(
            "OpenAI-compatible image recognition requires an exact model name.",
            code="CONFIG_INVALID",
        ) from None

    if isinstance(image_paths, (str, bytes, Path)):
        raise InvalidSource(
            "The provider image request requires an ordered image group.",
            code="SOURCE_INVALID",
        ) from None
    try:
        source_paths = tuple(Path(source) for source in image_paths)
    except Exception:
        raise InvalidSource(
            "The provider image request contains an invalid snapshot path.",
            code="SOURCE_INVALID",
        ) from None
    decoded_images = validate_image_group(source_paths)
    data_urls: list[str] = []
    for source_path, decoded in zip(source_paths, decoded_images, strict=True):
        source_bytes = _read_validated_snapshot(source_path)
        if decode_image_bytes(source_bytes, suffix=source_path.suffix) != decoded:
            raise InvalidSource(
                "A validated image snapshot changed during request preparation.",
                code="SOURCE_INVALID",
            ) from None
        mime_type = _MIME_TYPE_BY_FORMAT[decoded.format]
        try:
            encoded = base64.b64encode(source_bytes).decode("ascii")
        except MemoryError:
            raise InvalidSource(
                "The image request could not be encoded within memory limits.",
                code="SOURCE_TOO_LARGE",
            ) from None
        finally:
            del source_bytes
        data_urls.append(f"data:{mime_type};base64,{encoded}")
    return OpenAICompatibleImageRequest(
        _model=model,
        _prompt=prompt,
        _data_urls=tuple(data_urls),
    )


def _read_validated_snapshot(source_path: Path) -> bytes:
    expected_size = validate_source(source_path)
    try:
        with source_path.open("rb") as source_stream:
            source_bytes = source_stream.read(MAX_SOURCE_BYTES + 1)
    except FileNotFoundError:
        raise InvalidSource(
            "A validated image snapshot is no longer available.",
            code="SOURCE_NOT_FOUND",
        ) from None
    except (OSError, ValueError):
        raise InvalidSource(
            "A validated image snapshot cannot be read.",
            code="SOURCE_UNREADABLE",
        ) from None
    if len(source_bytes) > MAX_SOURCE_BYTES:
        raise InvalidSource(
            "A validated image snapshot exceeds the source limit.",
            code="SOURCE_TOO_LARGE",
        ) from None
    if len(source_bytes) != expected_size:
        raise InvalidSource(
            "A validated image snapshot changed during request preparation.",
            code="SOURCE_INVALID",
        ) from None
    return source_bytes
