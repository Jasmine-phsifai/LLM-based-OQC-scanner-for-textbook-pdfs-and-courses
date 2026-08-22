"""Persist and validate stable identities for repairable board-image batches."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from OCRLLM.core.write_text_atomically import write_text_atomically


_SCHEMA = "ocrllm.board_repair_manifest"
_VERSION = 1
_SUFFIX = ".board-repair.json"
_MAX_COMPATIBLE_PATH_CHARS = 240
_ALGORITHM = "board-source-batches-v1"
_BATCH_META_RE = re.compile(
    r"<!--\s*meta:board-batch\s+index=(\d+)\s+unit=([0-9a-f]{24})\s+"
    r"status=(complete|failed)\s*-->",
)


class BoardRepairIdentityError(Exception):
    """The saved output cannot be tied safely to the supplied board images."""


@dataclass(frozen=True)
class BoardRepairItem:
    index: int
    item_id: str
    display_name: str
    size: int
    sha256: str


@dataclass(frozen=True)
class BoardRepairBatch:
    index: int
    unit_id: str
    item_ids: tuple[str, ...]


@dataclass(frozen=True)
class BoardRepairManifest:
    items: tuple[BoardRepairItem, ...]
    batches: tuple[BoardRepairBatch, ...]
    request: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": _SCHEMA,
            "version": _VERSION,
            "algorithm": _ALGORITHM,
            "items": [asdict(item) for item in self.items],
            "batches": [
                {**asdict(batch), "item_ids": list(batch.item_ids)}
                for batch in self.batches
            ],
            "request": self.request,
        }


def board_repair_manifest_path(output_path: str | Path) -> Path:
    """Return the adjacent sidecar path for one board Markdown output."""
    output = Path(output_path)
    candidate = output.with_name(output.name + _SUFFIX)
    if len(str(candidate.resolve(strict=False))) <= _MAX_COMPATIBLE_PATH_CHARS:
        return candidate
    digest = hashlib.sha1(
        str(output.resolve(strict=False)).encode("utf-8", errors="surrogatepass")
    ).hexdigest()[:12]
    prefix = output.stem[:48].rstrip(" .") or "board"
    return output.with_name(f"{prefix}.{digest}{_SUFFIX}")


def create_board_repair_manifest(
    *,
    batches: Iterable[Iterable[str]],
    batch_size: int,
    prompt: str,
    skip_preprocess: bool,
) -> BoardRepairManifest:
    """Fingerprint the exact ordered sources and batch membership before dispatch."""
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
        raise BoardRepairIdentityError("板书修复身份 batch_size 无效")
    items: list[BoardRepairItem] = []
    saved_batches: list[BoardRepairBatch] = []
    for batch_index, paths in enumerate(batches, start=1):
        item_ids: list[str] = []
        for path_value in paths:
            size, digest = _fingerprint_local_file(path_value)
            item_index = len(items) + 1
            item_id = _item_id(item_index, size, digest)
            items.append(
                BoardRepairItem(
                    index=item_index,
                    item_id=item_id,
                    display_name=Path(path_value).name,
                    size=size,
                    sha256=digest,
                )
            )
            item_ids.append(item_id)
        if not item_ids:
            raise BoardRepairIdentityError("板书修复身份包含空批次")
        saved_batches.append(
            BoardRepairBatch(
                index=batch_index,
                unit_id=_batch_unit_id(batch_index, item_ids),
                item_ids=tuple(item_ids),
            )
        )
    if not items or not saved_batches:
        raise BoardRepairIdentityError("板书修复身份没有任何图片批次")
    return BoardRepairManifest(
        items=tuple(items),
        batches=tuple(saved_batches),
        request={
            "batch_size": batch_size,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "skip_preprocess": bool(skip_preprocess),
        },
    )


def save_board_repair_manifest(
    output_path: str | Path,
    manifest: BoardRepairManifest,
) -> None:
    """Atomically publish one versioned board-repair manifest."""
    payload = json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    write_text_atomically(board_repair_manifest_path(output_path), payload)


def load_board_repair_manifest(
    *,
    output_path: str | Path,
    markdown: str,
    supplied_paths: Iterable[str],
) -> tuple[BoardRepairManifest, dict[str, str]]:
    """Validate saved sources/batches and resolve them to current exact-byte paths."""
    path = board_repair_manifest_path(output_path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BoardRepairIdentityError(
            f"旧版板书输出缺少修复身份 manifest，无法安全修复: {path}"
        ) from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BoardRepairIdentityError(f"板书修复身份 manifest 无法读取: {path}: {exc}") from exc

    manifest = _parse_manifest(raw, path)
    _validate_markdown_batches(markdown, manifest.batches)
    resolved = _resolve_supplied_paths(manifest.items, tuple(supplied_paths))
    return manifest, resolved


def render_board_batch_marker(batch: BoardRepairBatch, status: str) -> str:
    """Render the stable machine marker for one complete or failed batch."""
    if status not in {"complete", "failed"}:
        raise ValueError(f"unsupported board batch status: {status}")
    return (
        f"<!-- meta:board-batch index={batch.index} unit={batch.unit_id} "
        f"status={status} -->"
    )


def render_board_batch_failure(batch: BoardRepairBatch, error: object) -> str:
    """Render a stable failed marker plus a human-readable sanitized error."""
    safe_error = str(error).replace("--", "\u2014")
    return (
        f"{render_board_batch_marker(batch, 'failed')}\n"
        f"<!-- board-batch-error: 批次 {batch.index} 识别失败: {safe_error} -->"
    )


def find_failed_board_batch_indices(markdown: str) -> list[int]:
    """Return failed batch indices from stable board metadata markers."""
    return [
        int(match.group(1))
        for match in _BATCH_META_RE.finditer(markdown)
        if match.group(3) == "failed"
    ]


def replace_failed_board_batch(
    markdown: str,
    batch: BoardRepairBatch,
    replacement_text: str,
) -> str:
    """Replace exactly one saved failed-batch block with completed content."""
    marker = re.escape(render_board_batch_marker(batch, "failed"))
    pattern = re.compile(
        rf"\s*{marker}\s*<!--\s*board-batch-error:.*?-->\s*",
        re.DOTALL,
    )
    completed = f"\n\n{render_board_batch_marker(batch, 'complete')}\n\n{replacement_text}\n\n"
    updated, count = pattern.subn(completed, markdown, count=1)
    if count != 1:
        raise BoardRepairIdentityError(
            f"板书修复标记已变化，无法安全发布批次 {batch.index}"
        )
    return updated


def _parse_manifest(raw: object, path: Path) -> BoardRepairManifest:
    if not isinstance(raw, dict):
        raise BoardRepairIdentityError(f"板书修复身份 manifest 顶层必须是对象: {path}")
    if (
        raw.get("schema") != _SCHEMA
        or raw.get("version") != _VERSION
        or raw.get("algorithm") != _ALGORITHM
    ):
        raise BoardRepairIdentityError(f"板书修复身份 manifest schema/version 不受支持: {path}")
    request = raw.get("request")
    if not isinstance(request, dict):
        raise BoardRepairIdentityError("板书修复身份 manifest request 无效")
    batch_size = request.get("batch_size")
    prompt_hash = request.get("prompt_sha256")
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
        raise BoardRepairIdentityError("板书修复身份 manifest request.batch_size 无效")
    if not isinstance(prompt_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", prompt_hash):
        raise BoardRepairIdentityError("板书修复身份 manifest request.prompt_sha256 无效")
    if not isinstance(request.get("skip_preprocess"), bool):
        raise BoardRepairIdentityError("板书修复身份 manifest request.skip_preprocess 无效")

    raw_items = raw.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise BoardRepairIdentityError("板书修复身份 manifest items 无效")
    items = tuple(
        _parse_item(item, expected_index=index)
        for index, item in enumerate(raw_items, start=1)
    )

    raw_batches = raw.get("batches")
    if not isinstance(raw_batches, list) or not raw_batches:
        raise BoardRepairIdentityError("板书修复身份 manifest batches 无效")
    batches = tuple(
        _parse_batch(batch, expected_index=index)
        for index, batch in enumerate(raw_batches, start=1)
    )
    if any(len(batch.item_ids) > batch_size for batch in batches):
        raise BoardRepairIdentityError("板书修复批次成员数超过保存的 batch_size")
    if tuple(item_id for batch in batches for item_id in batch.item_ids) != tuple(
        item.item_id for item in items
    ):
        raise BoardRepairIdentityError("板书修复批次必须按顺序完整覆盖原始图片")
    return BoardRepairManifest(items=items, batches=batches, request=dict(request))


def _parse_item(raw: object, *, expected_index: int) -> BoardRepairItem:
    if not isinstance(raw, dict) or raw.get("index") != expected_index:
        raise BoardRepairIdentityError("板书修复图片索引必须从 1 连续递增")
    size = raw.get("size")
    digest = raw.get("sha256")
    display_name = raw.get("display_name")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise BoardRepairIdentityError(f"板书修复图片 {expected_index} size 无效")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise BoardRepairIdentityError(f"板书修复图片 {expected_index} SHA-256 无效")
    if not isinstance(display_name, str) or not display_name:
        raise BoardRepairIdentityError(f"板书修复图片 {expected_index} display_name 无效")
    expected_id = _item_id(expected_index, size, digest)
    if raw.get("item_id") != expected_id:
        raise BoardRepairIdentityError(f"板书修复图片 {expected_index} 稳定身份无效")
    return BoardRepairItem(expected_index, expected_id, display_name, size, digest)


def _parse_batch(raw: object, *, expected_index: int) -> BoardRepairBatch:
    if not isinstance(raw, dict) or raw.get("index") != expected_index:
        raise BoardRepairIdentityError("板书修复批次索引必须从 1 连续递增")
    item_ids = raw.get("item_ids")
    if (
        not isinstance(item_ids, list)
        or not item_ids
        or not all(isinstance(item_id, str) for item_id in item_ids)
    ):
        raise BoardRepairIdentityError(f"板书修复批次 {expected_index} item_ids 无效")
    expected_unit = _batch_unit_id(expected_index, item_ids)
    if raw.get("unit_id") != expected_unit:
        raise BoardRepairIdentityError(f"板书修复批次 {expected_index} 稳定身份无效")
    return BoardRepairBatch(expected_index, expected_unit, tuple(item_ids))


def _validate_markdown_batches(
    markdown: str,
    batches: tuple[BoardRepairBatch, ...],
) -> None:
    found = [
        (int(match.group(1)), match.group(2), match.group(3))
        for match in _BATCH_META_RE.finditer(markdown)
    ]
    expected = [(batch.index, batch.unit_id) for batch in batches]
    if len(found) != len(expected) or [entry[:2] for entry in found] != expected:
        raise BoardRepairIdentityError("板书 Markdown 批次映射与修复 manifest 不一致")


def _resolve_supplied_paths(
    items: tuple[BoardRepairItem, ...],
    supplied_paths: tuple[str, ...],
) -> dict[str, str]:
    if len(supplied_paths) != len(items):
        raise BoardRepairIdentityError("提供的板书图片数量与修复 manifest 不一致")
    buckets: dict[tuple[int, str], list[str]] = defaultdict(list)
    for path in supplied_paths:
        buckets[_fingerprint_local_file(path)].append(path)
    resolved: dict[str, str] = {}
    for item in items:
        candidates = buckets.get((item.size, item.sha256))
        if not candidates:
            raise BoardRepairIdentityError(
                f"板书图片 {item.index} 指纹与修复 manifest 不一致，拒绝付费修复"
            )
        resolved[item.item_id] = candidates.pop(0)
    if any(paths for paths in buckets.values()):
        raise BoardRepairIdentityError("提供的板书图片集合与修复 manifest 不一致")
    return resolved


def _fingerprint_local_file(path_value: str) -> tuple[int, str]:
    path = Path(path_value)
    try:
        size = path.stat().st_size
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise BoardRepairIdentityError(f"无法读取板书图片并计算指纹: {path}: {exc}") from exc
    return size, digest.hexdigest()


def _item_id(index: int, size: int, digest: str) -> str:
    raw = f"{_ALGORITHM}:item:{index}:{size}:{digest}"
    return hashlib.sha256(raw.encode("ascii")).hexdigest()[:24]


def _batch_unit_id(index: int, item_ids: Iterable[str]) -> str:
    raw = ":".join((_ALGORITHM, "batch", str(index), *item_ids))
    return hashlib.sha256(raw.encode("ascii")).hexdigest()[:24]
