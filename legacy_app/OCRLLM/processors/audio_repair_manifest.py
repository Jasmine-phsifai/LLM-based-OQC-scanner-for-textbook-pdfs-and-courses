"""Persist and validate stable identities for repairable short-audio segments."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from OCRLLM.core.write_text_atomically import write_text_atomically


_SCHEMA = "ocrllm.audio_repair_manifest"
_VERSION = 1
_SUFFIX = ".audio-repair.json"
_MAX_COMPATIBLE_PATH_CHARS = 240
_SEGMENT_META_RE = re.compile(
    r"<!--\s*meta:segment\s+index=(\d+)\s+time=([^\s>]+)\s*-->",
)


class AudioRepairIdentityError(Exception):
    """The saved output cannot be tied safely to the supplied audio source."""


@dataclass(frozen=True)
class AudioRepairSegment:
    index: int
    unit_id: str
    actual_start_ms: int
    actual_end_ms: int
    logical_start_ms: int
    logical_end_ms: int
    display_time: str


@dataclass(frozen=True)
class AudioRepairManifest:
    source: dict[str, object]
    asr_input: dict[str, object]
    input_duration_ms: int
    splitter: dict[str, object]
    request: dict[str, object]
    segments: tuple[AudioRepairSegment, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": _SCHEMA,
            "version": _VERSION,
            "source": self.source,
            "asr_input": self.asr_input,
            "input_duration_ms": self.input_duration_ms,
            "splitter": self.splitter,
            "request": self.request,
            "segments": [asdict(segment) for segment in self.segments],
        }


def audio_repair_manifest_path(output_path: str | Path) -> Path:
    """Return the adjacent sidecar path for one audio Markdown output."""
    output = Path(output_path)
    candidate = output.with_name(output.name + _SUFFIX)
    if len(str(candidate.resolve(strict=False))) <= _MAX_COMPATIBLE_PATH_CHARS:
        return candidate

    digest = hashlib.sha1(
        str(output.resolve(strict=False)).encode("utf-8", errors="surrogatepass")
    ).hexdigest()[:12]
    prefix = output.stem[:48].rstrip(" .") or "audio"
    return output.with_name(f"{prefix}.{digest}{_SUFFIX}")


def create_audio_repair_manifest(
    *,
    source_path: str,
    asr_input_path: str,
    boundaries: Iterable[tuple[float, float, float, float]],
    input_duration: float,
    fallback_mode: bool,
    chunk_seconds: int,
    context_seconds: int,
    model: str,
    prompt: str,
    hotwords: Iterable[str],
) -> AudioRepairManifest:
    """Capture source bytes and exact segment windows before provider dispatch."""
    source = _fingerprint_local_file(source_path)
    asr_input = source if _same_file(source_path, asr_input_path) else _fingerprint_local_file(asr_input_path)
    splitter = {
        "algorithm": "short-asr-v1",
        "fallback_mode": bool(fallback_mode),
        "chunk_seconds": int(chunk_seconds),
        "context_seconds": int(context_seconds),
    }
    segments = tuple(
        _create_segment(index, window, str(asr_input["sha256"]), str(splitter["algorithm"]))
        for index, window in enumerate(boundaries, start=1)
    )
    if not segments:
        raise AudioRepairIdentityError("音频修复身份没有任何分段")
    return AudioRepairManifest(
        source=source,
        asr_input=asr_input,
        input_duration_ms=_seconds_to_ms(input_duration),
        splitter=splitter,
        request={
            "model": str(model),
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "hotwords_sha256": hashlib.sha256(
                json.dumps(list(hotwords), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        },
        segments=segments,
    )


def save_audio_repair_manifest(output_path: str | Path, manifest: AudioRepairManifest) -> None:
    """Atomically publish one versioned repair manifest beside its Markdown."""
    payload = json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    write_text_atomically(audio_repair_manifest_path(output_path), payload)


def load_audio_repair_manifest(
    *,
    output_path: str | Path,
    markdown: str,
    source_path: str,
    asr_input_path: str,
) -> AudioRepairManifest:
    """Load a manifest and prove that source bytes and Markdown units still match."""
    path = audio_repair_manifest_path(output_path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AudioRepairIdentityError(
            f"旧版音频输出缺少修复身份 manifest，无法安全修复: {path}"
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise AudioRepairIdentityError(f"音频修复身份 manifest 无法读取: {path}: {exc}") from exc

    manifest = _parse_manifest(raw, path)
    if not _fingerprints_match(manifest.source, _fingerprint_local_file(source_path)):
        raise AudioRepairIdentityError("音频源文件指纹与修复 manifest 不一致，拒绝付费修复")
    if not _fingerprints_match(manifest.asr_input, _fingerprint_local_file(asr_input_path)):
        raise AudioRepairIdentityError("实际 ASR 输入指纹与修复 manifest 不一致，拒绝付费修复")
    _validate_markdown_segments(markdown, manifest.segments)
    return manifest


def _parse_manifest(raw: object, path: Path) -> AudioRepairManifest:
    if not isinstance(raw, dict):
        raise AudioRepairIdentityError(f"音频修复身份 manifest 顶层必须是对象: {path}")
    if raw.get("schema") != _SCHEMA or raw.get("version") != _VERSION:
        raise AudioRepairIdentityError(f"音频修复身份 manifest schema/version 不受支持: {path}")

    source = _parse_fingerprint(raw.get("source"), "source")
    asr_input = _parse_fingerprint(raw.get("asr_input"), "asr_input")
    input_duration_ms = _require_positive_int(raw.get("input_duration_ms"), "input_duration_ms")
    splitter = raw.get("splitter")
    request = raw.get("request")
    if not isinstance(splitter, dict) or splitter.get("algorithm") != "short-asr-v1":
        raise AudioRepairIdentityError("音频修复身份 manifest splitter 无效")
    if not isinstance(request, dict):
        raise AudioRepairIdentityError("音频修复身份 manifest request 无效")

    raw_segments = raw.get("segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise AudioRepairIdentityError("音频修复身份 manifest segments 无效")
    segments = tuple(
        _parse_segment(item, expected_index=index, source_hash=str(asr_input["sha256"]))
        for index, item in enumerate(raw_segments, start=1)
    )
    if segments[0].logical_start_ms != 0:
        raise AudioRepairIdentityError("音频修复逻辑分段必须从 0 开始")
    for previous, current in zip(segments, segments[1:]):
        if previous.logical_end_ms != current.logical_start_ms:
            raise AudioRepairIdentityError("音频修复逻辑分段必须连续且不重叠")
    if segments[-1].logical_end_ms != input_duration_ms:
        raise AudioRepairIdentityError("音频修复逻辑分段必须覆盖原始 ASR 输入时长")
    if any(segment.actual_end_ms > input_duration_ms for segment in segments):
        raise AudioRepairIdentityError("音频修复实际分段超出原始 ASR 输入时长")
    return AudioRepairManifest(
        source=source,
        asr_input=asr_input,
        input_duration_ms=input_duration_ms,
        splitter=dict(splitter),
        request=dict(request),
        segments=segments,
    )


def _parse_segment(raw: object, *, expected_index: int, source_hash: str) -> AudioRepairSegment:
    if not isinstance(raw, dict) or raw.get("index") != expected_index:
        raise AudioRepairIdentityError("音频修复分段索引必须从 1 连续递增")
    values = {
        name: _require_nonnegative_int(raw.get(name), name)
        for name in (
            "actual_start_ms",
            "actual_end_ms",
            "logical_start_ms",
            "logical_end_ms",
        )
    }
    if not (
        values["actual_start_ms"] < values["actual_end_ms"]
        and values["logical_start_ms"] < values["logical_end_ms"]
        and values["actual_start_ms"] <= values["logical_start_ms"]
        and values["logical_end_ms"] <= values["actual_end_ms"]
    ):
        raise AudioRepairIdentityError(f"音频修复分段 {expected_index} 时间边界无效")
    expected_display = _display_time(values["logical_start_ms"], values["logical_end_ms"])
    expected_id = _unit_id(
        source_hash,
        "short-asr-v1",
        values["actual_start_ms"],
        values["actual_end_ms"],
        values["logical_start_ms"],
        values["logical_end_ms"],
    )
    if raw.get("display_time") != expected_display or raw.get("unit_id") != expected_id:
        raise AudioRepairIdentityError(f"音频修复分段 {expected_index} 稳定身份无效")
    return AudioRepairSegment(
        index=expected_index,
        unit_id=expected_id,
        display_time=expected_display,
        **values,
    )


def _create_segment(
    index: int,
    window: tuple[float, float, float, float],
    source_hash: str,
    algorithm: str,
) -> AudioRepairSegment:
    actual_start_ms, actual_end_ms, logical_start_ms, logical_end_ms = (
        _seconds_to_ms(value) for value in window
    )
    return AudioRepairSegment(
        index=index,
        unit_id=_unit_id(
            source_hash,
            algorithm,
            actual_start_ms,
            actual_end_ms,
            logical_start_ms,
            logical_end_ms,
        ),
        actual_start_ms=actual_start_ms,
        actual_end_ms=actual_end_ms,
        logical_start_ms=logical_start_ms,
        logical_end_ms=logical_end_ms,
        display_time=_display_time(logical_start_ms, logical_end_ms),
    )


def _unit_id(source_hash: str, algorithm: str, *bounds: int) -> str:
    identity = ":".join((source_hash, algorithm, *(str(value) for value in bounds)))
    return hashlib.sha256(identity.encode("ascii")).hexdigest()[:24]


def _fingerprint_local_file(path_value: str) -> dict[str, object]:
    path = Path(path_value)
    try:
        size = path.stat().st_size
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise AudioRepairIdentityError(f"无法读取音频源文件并计算指纹: {path}: {exc}") from exc
    return {"size": size, "sha256": digest.hexdigest()}


def _parse_fingerprint(raw: object, label: str) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise AudioRepairIdentityError(f"音频修复身份 manifest {label} 指纹无效")
    size = raw.get("size")
    digest = raw.get("sha256")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise AudioRepairIdentityError(f"音频修复身份 manifest {label}.size 无效")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise AudioRepairIdentityError(f"音频修复身份 manifest {label}.sha256 无效")
    return {"size": size, "sha256": digest}


def _validate_markdown_segments(markdown: str, segments: tuple[AudioRepairSegment, ...]) -> None:
    observed = {int(index): display for index, display in _SEGMENT_META_RE.findall(markdown)}
    expected = {segment.index: segment.display_time for segment in segments}
    if observed != expected:
        raise AudioRepairIdentityError("Markdown 分段元数据与修复 manifest 不一致，拒绝付费修复")


def _fingerprints_match(left: dict[str, object], right: dict[str, object]) -> bool:
    return left.get("size") == right.get("size") and left.get("sha256") == right.get("sha256")


def _seconds_to_ms(value: float) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise AudioRepairIdentityError("音频修复分段包含无效时间")
    milliseconds = int(round(float(value) * 1000))
    if milliseconds < 0:
        raise AudioRepairIdentityError("音频修复分段包含负时间")
    return milliseconds


def _display_time(start_ms: int, end_ms: int) -> str:
    return f"{_format_milliseconds(start_ms)}~{_format_milliseconds(end_ms)}"


def _format_milliseconds(value: int) -> str:
    total_seconds = value // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


def _require_positive_int(value: object, label: str) -> int:
    parsed = _require_nonnegative_int(value, label)
    if parsed == 0:
        raise AudioRepairIdentityError(f"音频修复身份 manifest {label} 必须大于 0")
    return parsed


def _require_nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AudioRepairIdentityError(f"音频修复身份 manifest {label} 无效")
    return value


def _same_file(left: str, right: str) -> bool:
    return Path(left).resolve(strict=False) == Path(right).resolve(strict=False)
