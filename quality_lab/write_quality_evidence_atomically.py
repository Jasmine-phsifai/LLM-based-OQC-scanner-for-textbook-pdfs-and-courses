"""Secret-scan and atomically checkpoint one quality-evidence JSON file."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path


class QualityEvidenceWriteError(OSError):
    """Quality evidence could not be persisted without loss or disclosure."""


def write_quality_evidence_atomically(
    path: str | Path,
    evidence: Mapping[str, object],
    *,
    credential: str,
    forbidden_values: Sequence[str] = (),
    replace_existing: bool,
) -> str:
    """Write canonical UTF-8 JSON and return its SHA-256-compatible text."""

    target = Path(path)
    if type(replace_existing) is not bool:
        raise TypeError("replace_existing must be an exact boolean")
    if type(credential) is not str or not credential:
        raise TypeError("credential must be nonempty text for disclosure scanning")
    if isinstance(forbidden_values, (str, bytes)) or not isinstance(
        forbidden_values, Sequence
    ):
        raise TypeError("forbidden_values must be an ordered text sequence")
    forbidden = (credential, *tuple(forbidden_values))
    if any(type(value) is not str or not value for value in forbidden):
        raise TypeError("forbidden_values must contain nonempty exact text")
    if not isinstance(evidence, Mapping):
        raise TypeError("evidence must be a mapping")
    if _contains_forbidden_text(evidence, forbidden):
        raise QualityEvidenceWriteError(
            "quality evidence contained a forbidden sensitive value"
        )
    try:
        rendered = json.dumps(
            evidence,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        ) + "\n"
    except (TypeError, ValueError) as exc:
        raise QualityEvidenceWriteError("quality evidence is not strict JSON") from exc
    if any(
        json.dumps(value, ensure_ascii=False)[1:-1] in rendered
        for value in forbidden
    ):
        raise QualityEvidenceWriteError(
            "quality evidence contained a forbidden sensitive value"
        )

    parent = target.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise QualityEvidenceWriteError("evidence directory could not be created") from exc
    if target.is_symlink():
        raise QualityEvidenceWriteError("evidence path must not be a symlink")
    if not replace_existing and os.path.lexists(target):
        raise QualityEvidenceWriteError("evidence path already exists")
    if replace_existing and not target.is_file():
        raise QualityEvidenceWriteError("existing evidence checkpoint is missing")

    payload = rendered.encode("utf-8")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=parent,
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if replace_existing:
            os.replace(temporary_path, target)
        else:
            try:
                os.link(temporary_path, target)
            except (AttributeError, NotImplementedError, OSError) as exc:
                raise QualityEvidenceWriteError(
                    "initial evidence checkpoint could not be created exclusively"
                ) from exc
            temporary_path.unlink()
            temporary_path = None
    except QualityEvidenceWriteError:
        raise
    except OSError as exc:
        raise QualityEvidenceWriteError("quality evidence checkpoint failed") from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
    return rendered


def _contains_forbidden_text(value: object, forbidden: tuple[str, ...]) -> bool:
    if type(value) is str:
        return any(item in value for item in forbidden)
    if isinstance(value, Mapping):
        return any(
            _contains_forbidden_text(key, forbidden)
            or _contains_forbidden_text(item, forbidden)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden_text(item, forbidden) for item in value)
    return False
