"""Build one bounded native Google image request."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from ...errors import InvalidSource
from ...imaging.decode_image_bytes import decode_image_bytes
from ...raise_if_cancelled import raise_if_cancelled
from .google_genai_image_request import GoogleGenAIImageRequest, GoogleInlineImage


MAX_GOOGLE_INLINE_BYTES = 20_000_000
_WIRE_BODY_OVERHEAD_BYTES = 512
_WIRE_PART_OVERHEAD_BYTES = 128
_MIME_BY_FORMAT = {"JPEG": "image/jpeg", "PNG": "image/png"}


def build_google_genai_image_request(
    image_paths: Sequence[Path],
    *,
    prompt: str,
    model: str,
    cancellation: object | None = None,
) -> GoogleGenAIImageRequest:
    """Read bounded snapshots and reject an oversized wire body locally."""
    raise_if_cancelled(cancellation)
    paths = _coerce_paths(image_paths)
    wire_bytes = (
        _WIRE_BODY_OVERHEAD_BYTES
        + _json_string_byte_count(model)
        + _json_string_byte_count(prompt)
    )
    inline_bytes = 0
    images: list[GoogleInlineImage] = []
    for image_index, path in enumerate(paths):
        raise_if_cancelled(cancellation)
        data = _read_bounded(path, remaining_wire_bytes=MAX_GOOGLE_INLINE_BYTES - wire_bytes)
        decoded = decode_image_bytes(data, suffix=path.suffix)
        mime_type = _MIME_BY_FORMAT.get(decoded.format)
        if mime_type is None:
            raise InvalidSource(
                "The decoded image format is not valid for Google GenAI.",
                code="SOURCE_INVALID",
                details={"image_index": image_index},
            ) from None
        wire_bytes += (
            4 * ((len(data) + 2) // 3)
            + _json_string_byte_count(mime_type)
            + _WIRE_PART_OVERHEAD_BYTES
        )
        if wire_bytes > MAX_GOOGLE_INLINE_BYTES:
            raise InvalidSource(
                "The Google GenAI image request exceeds the inline wire limit.",
                code="SOURCE_TOO_LARGE",
                details={"maximum_inline_wire_bytes": MAX_GOOGLE_INLINE_BYTES},
            ) from None
        inline_bytes += len(data)
        images.append(GoogleInlineImage(data=data, mime_type=mime_type))
    return GoogleGenAIImageRequest(
        model=model,
        contents=(*images, prompt),
        inline_byte_count=inline_bytes,
        wire_byte_upper_bound=wire_bytes,
    )


def _json_string_byte_count(value: str) -> int:
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def _coerce_paths(image_paths: Sequence[Path]) -> tuple[Path, ...]:
    if isinstance(image_paths, (str, bytes, Path)):
        raise InvalidSource("Google GenAI requires an ordered image group.") from None
    try:
        paths = tuple(Path(path) for path in image_paths)
    except Exception:
        raise InvalidSource("The Google GenAI image group is invalid.") from None
    if not paths:
        raise InvalidSource("Google GenAI requires at least one image.") from None
    return paths


def _read_bounded(path: Path, *, remaining_wire_bytes: int) -> bytes:
    maximum_source_bytes = max(0, (remaining_wire_bytes // 4) * 3)
    try:
        expected_size = path.stat().st_size
        with path.open("rb") as stream:
            data = stream.read(maximum_source_bytes + 1)
    except FileNotFoundError:
        raise InvalidSource(
            "A validated image snapshot is no longer available.",
            code="SOURCE_NOT_FOUND",
        ) from None
    except MemoryError:
        raise InvalidSource(
            "The Google GenAI image request cannot fit within memory limits.",
            code="SOURCE_TOO_LARGE",
        ) from None
    except (OSError, ValueError):
        raise InvalidSource(
            "A validated image snapshot cannot be read.",
            code="SOURCE_UNREADABLE",
        ) from None
    if len(data) > maximum_source_bytes:
        raise InvalidSource(
            "The Google GenAI image request exceeds the inline wire limit.",
            code="SOURCE_TOO_LARGE",
            details={"maximum_inline_wire_bytes": MAX_GOOGLE_INLINE_BYTES},
        ) from None
    if len(data) != expected_size:
        raise InvalidSource(
            "A validated image snapshot changed during Google preflight.",
            code="SOURCE_INVALID",
        ) from None
    return data
