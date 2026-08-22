import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from OCRLLM.core.provider_errors import ProviderSetupError
from OCRLLM.core.task_runner import CancelledError
from OCRLLM.processors.audio import AudioChunk, AudioProcessor
from OCRLLM.processors.audio_repair_manifest import (
    AudioRepairIdentityError,
    AudioRepairSegment,
    audio_repair_manifest_path,
)


class _ScriptedAudioLLM:
    def __init__(self, responses):
        self._responses = iter(responses)
        self.calls = 0

    def transcribe_short_audio(self, **_kwargs):
        self.calls += 1
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        return response


def _audio_processor(tmp_path: Path, responses):
    chunk_paths = [tmp_path / "chunk-1.mp3", tmp_path / "chunk-2.mp3"]
    for path in chunk_paths:
        path.write_bytes(b"chunk")
    processor = AudioProcessor.__new__(AudioProcessor)
    processor.cfg = SimpleNamespace(models=SimpleNamespace(asr_short_model="test-asr"))
    processor.llm = _ScriptedAudioLLM(responses)
    processor._ensure_upload_format = lambda path: path
    processor._should_use_short_asr = lambda _path: (True, 2.0)
    processor._split_audio = lambda _path, duration: [
        SimpleNamespace(path=str(path)) for path in chunk_paths
    ]
    processor._split_audio_from_repair_manifest = lambda _path, segments, _duration: {
        segment.index: SimpleNamespace(path=str(chunk_paths[segment.index - 1]))
        for segment in segments
    }
    processor._build_system_prompt = lambda *_args: "prompt"
    processor._report = lambda *_args: None
    processor._check_cancelled = lambda: None
    processor._report_content = lambda *_args: None
    return processor


def _write_repair_manifest(
    audio_path: Path,
    md_path: Path,
    boundaries=((0, 1000), (1000, 2000)),
):
    source_hash = hashlib.sha256(audio_path.read_bytes()).hexdigest()
    segments = []
    for index, (start_ms, end_ms) in enumerate(boundaries, start=1):
        unit_identity = ":".join(
            (source_hash, "short-asr-v1", str(start_ms), str(end_ms), str(start_ms), str(end_ms))
        )
        segments.append(
            {
                "index": index,
                "unit_id": hashlib.sha256(unit_identity.encode("ascii")).hexdigest()[:24],
                "actual_start_ms": start_ms,
                "actual_end_ms": end_ms,
                "logical_start_ms": start_ms,
                "logical_end_ms": end_ms,
                "display_time": f"00:0{index - 1}~00:0{index}",
            }
        )
    payload = {
        "schema": "ocrllm.audio_repair_manifest",
        "version": 1,
        "source": {"size": audio_path.stat().st_size, "sha256": source_hash},
        "asr_input": {"size": audio_path.stat().st_size, "sha256": source_hash},
        "input_duration_ms": boundaries[-1][1],
        "splitter": {"algorithm": "short-asr-v1", "fallback_mode": False},
        "request": {"model": "test-asr", "prompt_sha256": "test"},
        "segments": segments,
    }
    Path(str(md_path) + ".audio-repair.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def test_audio_repair_publishes_success_before_cancellation(tmp_path):
    audio_path = tmp_path / "lecture.mp3"
    md_path = tmp_path / "lecture.md"
    audio_path.write_bytes(b"audio")
    md_path.write_text(
        "<!-- meta:segment index=1 time=00:00~00:01 -->\n"
        "（分段 1 识别失败: timeout）\n\n"
        "<!-- meta:segment index=2 time=00:01~00:02 -->\n"
        "（分段 2 识别失败: timeout）",
        encoding="utf-8",
    )
    _write_repair_manifest(audio_path, md_path)
    processor = _audio_processor(
        tmp_path,
        ["第一段已修复", CancelledError("任务已取消")],
    )

    with pytest.raises(CancelledError):
        processor.repair(str(audio_path), str(md_path))

    content = md_path.read_text(encoding="utf-8")
    assert "第一段已修复" in content
    assert "分段 1 识别失败" not in content
    assert "分段 2 识别失败" in content


def test_audio_repair_propagates_provider_setup_errors(tmp_path):
    audio_path = tmp_path / "lecture.mp3"
    md_path = tmp_path / "lecture.md"
    audio_path.write_bytes(b"audio")
    md_path.write_text(
        "<!-- meta:segment index=1 time=00:00~00:01 -->\n"
        "（分段 1 识别失败: timeout）",
        encoding="utf-8",
    )
    _write_repair_manifest(audio_path, md_path, boundaries=((0, 1000),))
    processor = _audio_processor(
        tmp_path,
        [ProviderSetupError("provider SDK missing")],
    )

    with pytest.raises(ProviderSetupError, match="provider SDK missing"):
        processor.repair(str(audio_path), str(md_path))

    assert "分段 1 识别失败" in md_path.read_text(encoding="utf-8")


def test_audio_repair_uses_saved_boundaries_instead_of_current_split_config(tmp_path):
    audio_path = tmp_path / "lecture.mp3"
    md_path = tmp_path / "lecture.md"
    audio_path.write_bytes(b"original audio")
    md_path.write_text(
        "<!-- meta:segment index=1 time=00:00~00:01 -->\n第一段\n\n"
        "<!-- meta:segment index=2 time=00:01~00:02 -->\n"
        "（分段 2 识别失败: timeout）",
        encoding="utf-8",
    )
    _write_repair_manifest(audio_path, md_path)
    processor = _audio_processor(tmp_path, ["第二段已修复"])
    selected = []

    def split_from_manifest(_path, segments, _duration_ms):
        selected.extend(
            (segment.index, segment.actual_start_ms, segment.actual_end_ms)
            for segment in segments
        )
        return {2: SimpleNamespace(path=str(tmp_path / "chunk-2.mp3"))}

    processor._split_audio = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("current split configuration must not be consulted")
    )
    processor._split_audio_from_repair_manifest = split_from_manifest

    processor.repair(str(audio_path), str(md_path))

    assert selected == [(2, 1000, 2000)]
    assert "第二段已修复" in md_path.read_text(encoding="utf-8")


def test_audio_repair_rejects_source_byte_drift_before_provider_call(tmp_path):
    audio_path = tmp_path / "lecture.mp3"
    md_path = tmp_path / "lecture.md"
    audio_path.write_bytes(b"first-source")
    md_path.write_text(
        "<!-- meta:segment index=1 time=00:00~00:01 -->\n"
        "（分段 1 识别失败: timeout）",
        encoding="utf-8",
    )
    _write_repair_manifest(audio_path, md_path, boundaries=((0, 1000),))
    audio_path.write_bytes(b"other-source")
    processor = _audio_processor(tmp_path, ["must not run"])

    with pytest.raises(AudioRepairIdentityError, match="source|源文件|指纹"):
        processor.repair(str(audio_path), str(md_path))

    assert processor.llm.calls == 0
    assert "分段 1 识别失败" in md_path.read_text(encoding="utf-8")


def test_audio_repair_rejects_missing_identity_before_provider_call(tmp_path):
    audio_path = tmp_path / "lecture.mp3"
    md_path = tmp_path / "lecture.md"
    audio_path.write_bytes(b"audio")
    md_path.write_text(
        "<!-- meta:segment index=1 time=00:00~00:01 -->\n"
        "（分段 1 识别失败: timeout）",
        encoding="utf-8",
    )
    processor = _audio_processor(tmp_path, ["must not run"])

    with pytest.raises(AudioRepairIdentityError, match="manifest|身份|旧版"):
        processor.repair(str(audio_path), str(md_path))

    assert processor.llm.calls == 0
    assert "分段 1 识别失败" in md_path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "manifest_text",
    [
        "{not-json",
        json.dumps({"schema": "ocrllm.audio_repair_manifest", "version": 999}),
    ],
)
def test_audio_repair_rejects_invalid_identity_before_provider_call(
    tmp_path,
    manifest_text,
):
    audio_path = tmp_path / "lecture.mp3"
    md_path = tmp_path / "lecture.md"
    audio_path.write_bytes(b"audio")
    md_path.write_text(
        "<!-- meta:segment index=1 time=00:00~00:01 -->\n"
        "（分段 1 识别失败: timeout）",
        encoding="utf-8",
    )
    Path(str(md_path) + ".audio-repair.json").write_text(manifest_text, encoding="utf-8")
    processor = _audio_processor(tmp_path, ["must not run"])

    with pytest.raises(AudioRepairIdentityError, match="manifest"):
        processor.repair(str(audio_path), str(md_path))

    assert processor.llm.calls == 0


def test_audio_repair_rejects_markdown_segment_drift_before_provider_call(tmp_path):
    audio_path = tmp_path / "lecture.mp3"
    md_path = tmp_path / "lecture.md"
    audio_path.write_bytes(b"audio")
    md_path.write_text(
        "<!-- meta:segment index=1 time=00:00~00:01 -->\n"
        "（分段 1 识别失败: timeout）",
        encoding="utf-8",
    )
    _write_repair_manifest(audio_path, md_path, boundaries=((0, 1000),))
    md_path.write_text(
        "<!-- meta:segment index=1 time=00:00~00:02 -->\n"
        "（分段 1 识别失败: timeout）",
        encoding="utf-8",
    )
    processor = _audio_processor(tmp_path, ["must not run"])

    with pytest.raises(AudioRepairIdentityError, match="Markdown|manifest"):
        processor.repair(str(audio_path), str(md_path))

    assert processor.llm.calls == 0


def test_audio_repair_manifest_shortens_deep_output_names(tmp_path):
    output_path = tmp_path / (("lecture" * 30) + ".md")

    manifest_path = audio_repair_manifest_path(output_path)

    assert manifest_path.parent == tmp_path
    assert manifest_path.name.endswith(".audio-repair.json")
    assert len(manifest_path.name) < len(output_path.name)


def test_short_asr_persists_source_hash_and_exact_segment_boundaries(tmp_path):
    audio_path = tmp_path / "lecture.mp3"
    output_path = tmp_path / "lecture.md"
    audio_path.write_bytes(b"source-audio")
    processor = _audio_processor(tmp_path, ["transcribed"])
    processor.cfg = SimpleNamespace(
        models=SimpleNamespace(asr_short_model="test-asr"),
        processing=SimpleNamespace(
            asr_short_chunk_seconds=60,
            asr_fallback_chunk_seconds=30,
            asr_fallback_context_seconds=5,
        ),
        concurrency=SimpleNamespace(audio_asr_parallel_requests=1),
    )
    processor._split_audio = lambda *_args, **_kwargs: [
        AudioChunk(str(audio_path), 0.0, 2.0, 0.0, 2.0),
    ]

    processor._short_asr(
        str(audio_path),
        ["术语"],
        str(output_path),
        duration=2.0,
        source_path=str(audio_path),
    )

    manifest = json.loads(audio_repair_manifest_path(output_path).read_text(encoding="utf-8"))
    assert manifest["schema"] == "ocrllm.audio_repair_manifest"
    assert manifest["version"] == 1
    assert manifest["source"]["sha256"] == hashlib.sha256(b"source-audio").hexdigest()
    assert manifest["segments"] == [
        {
            "actual_end_ms": 2000,
            "actual_start_ms": 0,
            "display_time": "00:00~00:02",
            "index": 1,
            "logical_end_ms": 2000,
            "logical_start_ms": 0,
            "unit_id": manifest["segments"][0]["unit_id"],
        }
    ]
    assert len(manifest["segments"][0]["unit_id"]) == 24


def test_audio_repair_materializes_the_saved_window_without_current_config(
    tmp_path,
    monkeypatch,
):
    audio_path = tmp_path / "lecture.mp3"
    audio_path.write_bytes(b"audio")
    processor = _audio_processor(tmp_path, [])
    processor._split_audio_from_repair_manifest = (
        AudioProcessor._split_audio_from_repair_manifest.__get__(processor, AudioProcessor)
    )
    processor.cfg = SimpleNamespace(paths=SimpleNamespace(temp_dir=str(tmp_path)))
    processor.reporter = SimpleNamespace(cancel_event=None)
    segment = AudioRepairSegment(
        index=2,
        unit_id="stable-window-id",
        actual_start_ms=1000,
        actual_end_ms=2500,
        logical_start_ms=1250,
        logical_end_ms=2250,
        display_time="00:01~00:02",
    )
    commands = []
    monkeypatch.setattr("OCRLLM.processors.audio.get_ffmpeg", lambda: "ffmpeg-test")
    monkeypatch.setattr(
        "OCRLLM.processors.audio.run_subprocess_cancellable",
        lambda command, **_kwargs: commands.append(command),
    )

    chunks = processor._split_audio_from_repair_manifest(
        str(audio_path),
        [segment],
        input_duration_ms=3000,
    )

    assert commands[0][:6] == [
        "ffmpeg-test",
        "-ss",
        "1.000",
        "-i",
        str(audio_path),
        "-t",
    ]
    assert commands[0][6] == "1.500"
    assert chunks[2].actual_start == 1.0
    assert chunks[2].actual_end == 2.5
    assert chunks[2].logical_start == 1.25
    assert chunks[2].logical_end == 2.25
